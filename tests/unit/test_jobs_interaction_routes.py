import json
import io
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")
from fastapi import BackgroundTasks, HTTPException, UploadFile

from server.config import config
from server.main import app
from server.models import (
    AuthMethod,
    AuthMethodSelection,
    ExecutionMode,
    InteractionReplyRequest,
    InteractionReplyResponse,
    RunCreateRequest,
    RunStatus,
    SkillManifest,
)
from server.routers import jobs as jobs_router
import server.services.orchestration.run_interaction_service as interaction_service_module
from server.services.orchestration.run_store import RunStore
from server.services.orchestration.run_workspace_layout import require_layout_from_record


def _create_skill(
    base_dir: Path,
    skill_id: str,
    *,
    execution_modes: list[str] | None = None,
) -> SkillManifest:
    skill_dir = base_dir / skill_id
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    modes = execution_modes or ["auto", "interactive"]
    (skill_dir / "SKILL.md").write_text("skill", encoding="utf-8")
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": skill_id,
                "engines": ["codex"],
                "execution_modes": modes,
            }
        ),
        encoding="utf-8",
    )
    return SkillManifest(
        id=skill_id,
        path=skill_dir,
        engines=["codex"],
        execution_modes=modes,
    )


def _patch_skill_registry(monkeypatch: pytest.MonkeyPatch, skill: SkillManifest) -> None:
    monkeypatch.setattr(
        jobs_router.skill_registry,
        "get_skill",
        lambda skill_id: skill if skill_id == skill.id else None,
    )


async def _write_status(
    store: RunStore,
    request_id: str,
    run_id: str,
    status: RunStatus,
) -> None:
    payload = {
        "request_id": request_id,
        "run_id": run_id,
        "status": status.value,
        "updated_at": "2026-02-16T00:00:00",
        "current_attempt": 1,
        "state_phase": {
            "waiting_auth_phase": None,
            "dispatch_phase": None,
        },
        "pending": {
            "owner": None,
            "interaction_id": None,
            "auth_session_id": None,
            "payload": None,
        },
        "resume": {
            "resume_ticket_id": None,
            "resume_cause": None,
            "source_attempt": None,
            "target_attempt": None,
        },
        "runtime": {
            "conversation_mode": "session",
            "requested_execution_mode": None,
            "effective_execution_mode": None,
            "effective_interactive_require_user_reply": None,
            "effective_interactive_reply_timeout_sec": None,
            "effective_session_timeout_sec": None,
        },
        "error": None,
        "warnings": [],
    }
    await store.set_run_state(request_id, payload)


async def _create_interactive_request(
    monkeypatch: pytest.MonkeyPatch,
    temp_config_dirs: Path,
    *,
    runtime_options: dict[str, object] | None = None,
) -> tuple[RunStore, str]:
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)
    monkeypatch.setattr("server.runtime.observability.run_source_adapter.run_store", store)
    monkeypatch.setattr(
        jobs_router.concurrency_manager,
        "admit_or_reject",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda _engine, model: {"model": model},
    )
    skill = _create_skill(temp_config_dirs, "demo-skill")
    _patch_skill_registry(monkeypatch, skill)

    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={},
            model="gpt-5.4-mini",
            runtime_options=runtime_options or {"execution_mode": "interactive"},
        ),
        BackgroundTasks(),
    )
    return store, response.request_id


@pytest.mark.asyncio
async def test_get_interaction_pending_returns_pending(monkeypatch, temp_config_dirs):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    request_record = await store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None

    await _write_status(store, request_id, run_id, RunStatus.WAITING_USER)
    await store.set_pending_interaction(
        request_id,
        {
            "interaction_id": 1,
            "kind": "choose_one",
            "prompt": "Select one",
            "options": [{"label": "A", "value": "a"}],
        },
    )

    response = await jobs_router.get_interaction_pending(request_id)
    assert response.status == RunStatus.WAITING_USER
    assert response.pending is not None
    assert response.pending.interaction_id == 1
    assert response.pending.kind.value == "choose_one"


@pytest.mark.asyncio
async def test_interaction_file_reply_publishes_managed_file_and_replays_once(
    monkeypatch,
    temp_config_dirs,
):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    request_record = await store.get_request(request_id)
    assert request_record is not None
    run_id = str(request_record["run_id"])
    layout = require_layout_from_record(request_record)
    await _write_status(store, request_id, run_id, RunStatus.WAITING_USER)
    await store.set_pending_interaction(
        request_id,
        {
            "interaction_id": 17,
            "kind": "upload_files",
            "prompt": "Upload the paper",
            "ui_hints": {
                "kind": "upload_files",
                "files": [{"name": "paper", "required": True, "accept": ".pdf"}],
            },
        },
    )
    metadata = json.dumps(
        {
            "interaction_id": 17,
            "idempotency_key": "17-key",
            "message": "Please read it",
            "bindings": [{"slot": "paper", "file_index": 0}],
        }
    )
    first_tasks = BackgroundTasks()
    first = await jobs_router.reply_interaction_files(
        request_id=request_id,
        background_tasks=first_tasks,
        metadata=[metadata],
        files=[UploadFile(filename="../folder\\paper.pdf", file=io.BytesIO(b"pdf"))],
    )
    record = await store.get_interaction_reply_record(request_id, 17, "17-key")
    assert record is not None
    managed = record["response"]["files"][0]
    managed_path = layout.workspace_dir / managed["path"]

    replay_tasks = BackgroundTasks()
    replay = await jobs_router.reply_interaction_files(
        request_id=request_id,
        background_tasks=replay_tasks,
        metadata=[metadata],
        files=[UploadFile(filename="paper.pdf", file=io.BytesIO(b"pdf"))],
    )

    assert first.status == RunStatus.QUEUED
    assert replay == first
    assert managed["name"] == "paper.pdf"
    assert managed_path.read_bytes() == b"pdf"
    assert "path" not in record["public_response"]["files"][0]
    assert len(first_tasks.tasks) == 1
    assert replay_tasks.tasks == []
    event_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in layout.audit_dir.glob("orchestrator_events.*.jsonl")
    )
    assert "response_summary" in event_text
    assert managed["path"] not in event_text
    receipt_dirs = [path for path in layout.interaction_reply_files_dir.rglob("*") if path.is_dir()]
    assert not any(path.name.startswith(".tmp-") for path in receipt_dirs)

    with pytest.raises(HTTPException) as exc_info:
        await jobs_router.reply_interaction_files(
            request_id=request_id,
            background_tasks=BackgroundTasks(),
            metadata=[metadata],
            files=[UploadFile(filename="paper.pdf", file=io.BytesIO(b"different"))],
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_interaction_file_reply_rejects_unknown_slot_without_consuming_pending(
    monkeypatch,
    temp_config_dirs,
):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    request_record = await store.get_request(request_id)
    assert request_record is not None
    run_id = str(request_record["run_id"])
    await _write_status(store, request_id, run_id, RunStatus.WAITING_USER)
    await store.set_pending_interaction(
        request_id,
        {
            "interaction_id": 18,
            "kind": "upload_files",
            "prompt": "Upload the paper",
            "ui_hints": {
                "kind": "upload_files",
                "files": [{"name": "paper", "required": True}],
            },
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        await jobs_router.reply_interaction_files(
            request_id=request_id,
            background_tasks=BackgroundTasks(),
            metadata=[json.dumps(
                {
                    "interaction_id": 18,
                    "idempotency_key": "18-key",
                    "bindings": [{"slot": "unknown", "file_index": 0}],
                }
            )],
            files=[UploadFile(filename="paper.pdf", file=io.BytesIO(b"pdf"))],
        )
    assert exc_info.value.status_code == 422
    assert await store.get_pending_interaction(request_id) is not None


@pytest.mark.asyncio
async def test_interaction_file_reply_real_multipart_smoke(
    monkeypatch,
    temp_config_dirs,
):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    request_record = await store.get_request(request_id)
    assert request_record is not None
    run_id = str(request_record["run_id"])
    await _write_status(store, request_id, run_id, RunStatus.WAITING_USER)
    await store.set_pending_interaction(
        request_id,
        {
            "interaction_id": 21,
            "kind": "upload_files",
            "prompt": "Upload",
            "ui_hints": {
                "kind": "upload_files",
                "files": [{"name": "paper", "required": True}],
            },
        },
    )
    resume = AsyncMock()
    monkeypatch.setattr(interaction_service_module.job_orchestrator, "run_job", resume)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            f"/v1/jobs/{request_id}/interaction/reply/files",
            data={
                "metadata": json.dumps(
                    {
                        "interaction_id": 21,
                        "idempotency_key": "21-smoke",
                        "bindings": [{"slot": "paper", "file_index": 0}],
                    }
                )
            },
            files=[("files", ("paper.pdf", b"smoke", "application/pdf"))],
        )

    assert response.status_code == 200
    assert response.json() == {
        "request_id": request_id,
        "status": "queued",
        "accepted": True,
        "mode": "interaction",
    }
    resume.assert_awaited_once()


@pytest.mark.asyncio
async def test_interaction_file_reply_enforces_stream_limit_and_rejects_empty_file(
    monkeypatch,
    temp_config_dirs,
):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    request_record = await store.get_request(request_id)
    assert request_record is not None
    run_id = str(request_record["run_id"])
    await _write_status(store, request_id, run_id, RunStatus.WAITING_USER)
    await store.set_pending_interaction(
        request_id,
        {
            "interaction_id": 22,
            "kind": "upload_files",
            "prompt": "Upload",
            "ui_hints": {
                "kind": "upload_files",
                "files": [{"name": "paper", "required": True}],
            },
        },
    )
    original_limit = int(config.SYSTEM.INTERACTION_FILES.MAX_FILE_BYTES)
    config.defrost()
    config.SYSTEM.INTERACTION_FILES.MAX_FILE_BYTES = 4
    config.freeze()
    try:
        with pytest.raises(HTTPException) as too_large:
            await jobs_router.reply_interaction_files(
                request_id=request_id,
                background_tasks=BackgroundTasks(),
                metadata=[json.dumps(
                    {
                        "interaction_id": 22,
                        "idempotency_key": "22-large",
                        "bindings": [{"slot": "paper", "file_index": 0}],
                    }
                )],
                files=[UploadFile(filename="paper.pdf", file=io.BytesIO(b"12345"))],
            )
    finally:
        config.defrost()
        config.SYSTEM.INTERACTION_FILES.MAX_FILE_BYTES = original_limit
        config.freeze()

    with pytest.raises(HTTPException) as empty:
        await jobs_router.reply_interaction_files(
            request_id=request_id,
            background_tasks=BackgroundTasks(),
            metadata=[json.dumps(
                {
                    "interaction_id": 22,
                    "idempotency_key": "22-empty",
                    "bindings": [{"slot": "paper", "file_index": 0}],
                }
            )],
            files=[UploadFile(filename="paper.pdf", file=io.BytesIO(b""))],
        )

    assert too_large.value.status_code == 413
    assert empty.value.status_code == 422
    assert await store.get_pending_interaction(request_id) is not None


@pytest.mark.asyncio
async def test_get_run_status_exposes_waiting_user_pending_fields(monkeypatch, temp_config_dirs):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    request_record = await store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None

    await _write_status(store, request_id, run_id, RunStatus.WAITING_USER)
    await store.set_pending_interaction(
        request_id,
        {
            "interaction_id": 11,
            "kind": "open_text",
            "prompt": "Need your input",
        },
    )

    response = await jobs_router.get_run_status(request_id)
    assert response.status == RunStatus.WAITING_USER
    assert response.pending_interaction_id == 11
    assert response.interaction_count == 1
    assert response.recovery_state.value == "none"
    assert response.recovered_at is None
    assert response.recovery_reason is None


@pytest.mark.asyncio
async def test_get_run_status_waiting_auth_uses_persisted_audit_directory(
    monkeypatch,
    temp_config_dirs,
):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    request_record = await store.get_request(request_id)
    assert request_record is not None
    run_id = str(request_record["run_id"])
    layout = require_layout_from_record(request_record)
    await _write_status(store, request_id, run_id, RunStatus.WAITING_AUTH)
    reconcile = AsyncMock()
    monkeypatch.setattr(
        "server.services.orchestration.run_auth_orchestration_service."
        "run_auth_orchestration_service.reconcile_waiting_auth",
        reconcile,
    )

    response = await jobs_router.get_run_status(request_id)

    assert response.status == RunStatus.WAITING_AUTH
    reconcile.assert_awaited_once_with(request_id=request_id)
    assert (layout.audit_dir / "service.run.log").is_file()
    assert not (layout.workspace_dir / ".audit" / "service.run.log").exists()


@pytest.mark.asyncio
async def test_get_run_status_exposes_interactive_auto_reply_fields(monkeypatch, temp_config_dirs):
    store, request_id = await _create_interactive_request(
        monkeypatch,
        temp_config_dirs,
        runtime_options={
            "execution_mode": "interactive",
            "interactive_auto_reply": True,
            "interactive_reply_timeout_sec": 5,
        },
    )
    request_record = await store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None

    await _write_status(store, request_id, run_id, RunStatus.WAITING_USER)
    response = await jobs_router.get_run_status(request_id)
    assert response.status == RunStatus.WAITING_USER
    assert response.interactive_auto_reply is True
    assert response.interactive_reply_timeout_sec == 5
    assert response.requested_execution_mode.value == "interactive"
    assert response.effective_execution_mode.value == "interactive"
    assert response.conversation_mode.value == "session"
    assert response.effective_interactive_require_user_reply is True
    assert response.effective_interactive_reply_timeout_sec == 5


@pytest.mark.asyncio
async def test_create_run_normalizes_non_session_dual_mode_skill_to_auto(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)
    monkeypatch.setattr(
        jobs_router.concurrency_manager,
        "admit_or_reject",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda _engine, model: {"model": model},
    )
    skill = _create_skill(temp_config_dirs, "dual-mode-skill", execution_modes=["auto", "interactive"])
    _patch_skill_registry(monkeypatch, skill)

    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={},
            model="gpt-5.4-mini",
            runtime_options={"execution_mode": "interactive"},
            client_metadata={"conversation_mode": "non_session"},
        ),
        BackgroundTasks(),
    )
    request_record = await store.get_request(response.request_id)
    assert request_record is not None
    assert request_record["runtime_options"]["execution_mode"] == "interactive"
    assert request_record["effective_runtime_options"]["execution_mode"] == "auto"
    assert request_record["client_metadata"]["conversation_mode"] == "non_session"


@pytest.mark.asyncio
async def test_create_run_normalizes_non_session_interactive_only_skill_to_zero_timeout(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)
    monkeypatch.setattr(
        jobs_router.concurrency_manager,
        "admit_or_reject",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda _engine, model: {"model": model},
    )
    skill = _create_skill(temp_config_dirs, "interactive-only-skill", execution_modes=["interactive"])
    _patch_skill_registry(monkeypatch, skill)

    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={},
            model="gpt-5.4-mini",
            runtime_options={},
            client_metadata={"conversation_mode": "non_session"},
        ),
        BackgroundTasks(),
    )
    request_record = await store.get_request(response.request_id)
    assert request_record is not None
    assert request_record["effective_runtime_options"]["execution_mode"] == "interactive"
    assert request_record["effective_runtime_options"]["interactive_auto_reply"] is True
    assert request_record["effective_runtime_options"]["interactive_reply_timeout_sec"] == 0


@pytest.mark.asyncio
async def test_reply_interaction_accepts_and_transitions_to_queued(monkeypatch, temp_config_dirs):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    monkeypatch.setattr(jobs_router.concurrency_manager, "admit_or_reject", AsyncMock(return_value=True))
    appended_events: list[dict[str, object]] = []
    monkeypatch.setattr(
        jobs_router.job_orchestrator.audit_service,
        "append_orchestrator_event",
        lambda **kwargs: appended_events.append(dict(kwargs)),
    )
    request_record = await store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None

    await _write_status(store, request_id, run_id, RunStatus.WAITING_USER)
    await store.set_pending_interaction(
        request_id,
        {
            "interaction_id": 3,
            "kind": "confirm",
            "prompt": "Continue?",
        },
    )

    response = await jobs_router.reply_interaction(
        request_id,
        InteractionReplyRequest(
            interaction_id=3,
            response={"confirm": True},
            idempotency_key="k-1",
        ),
        BackgroundTasks(),
    )
    assert response.accepted is True
    assert response.status == RunStatus.QUEUED
    assert len(appended_events) == 1
    assert appended_events[0]["type_name"] == "interaction.reply.accepted"
    assert appended_events[0]["attempt_number"] == 2
    assert appended_events[0]["category"] == "interaction"
    assert appended_events[0]["audit_dir"] == (
        Path(request_record["input_manifest_path"]).parent
    )
    assert appended_events[0]["data"] == {
        "interaction_id": 3,
        "resolution_mode": "user_reply",
        "accepted_at": appended_events[0]["data"]["accepted_at"],
        "response_preview": None,
    }

    idempotent = await jobs_router.reply_interaction(
        request_id,
        InteractionReplyRequest(
            interaction_id=3,
            response={"confirm": True},
            idempotency_key="k-1",
        ),
        BackgroundTasks(),
    )
    assert idempotent.accepted is True
    assert idempotent.status == RunStatus.QUEUED
    assert len(appended_events) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind",
    ["choose_one", "confirm", "fill_fields", "open_text", "upload_files", "risk_ack"],
)
async def test_reply_interaction_accepts_free_text_for_all_supported_kinds(
    monkeypatch,
    temp_config_dirs,
    kind: str,
):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    monkeypatch.setattr(jobs_router.concurrency_manager, "admit_or_reject", AsyncMock(return_value=True))
    request_record = await store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None

    await _write_status(store, request_id, run_id, RunStatus.WAITING_USER)
    await store.set_pending_interaction(
        request_id,
        {
            "interaction_id": 30,
            "kind": kind,
            "prompt": "continue?",
            "default_decision_policy": "engine_judgement",
        },
    )

    response = await jobs_router.reply_interaction(
        request_id,
        InteractionReplyRequest(
            interaction_id=30,
            response="继续执行",
            idempotency_key=f"text-{kind}",
        ),
        BackgroundTasks(),
    )
    assert response.accepted is True
    assert response.status == RunStatus.QUEUED


@pytest.mark.asyncio
async def test_reply_interaction_appends_response_preview_for_open_text(monkeypatch, temp_config_dirs):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    monkeypatch.setattr(jobs_router.concurrency_manager, "admit_or_reject", AsyncMock(return_value=True))
    appended_events: list[dict[str, object]] = []
    monkeypatch.setattr(
        jobs_router.job_orchestrator.audit_service,
        "append_orchestrator_event",
        lambda **kwargs: appended_events.append(dict(kwargs)),
    )
    request_record = await store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None

    await _write_status(store, request_id, run_id, RunStatus.WAITING_USER)
    await store.set_pending_interaction(
        request_id,
        {
            "interaction_id": 31,
            "kind": "open_text",
            "prompt": "continue?",
        },
    )

    response = await jobs_router.reply_interaction(
        request_id,
        InteractionReplyRequest(
            interaction_id=31,
            response="继续执行",
            idempotency_key="preview-open-text",
        ),
        BackgroundTasks(),
    )

    assert response.accepted is True
    assert response.status == RunStatus.QUEUED
    assert len(appended_events) == 1
    assert appended_events[0]["type_name"] == "interaction.reply.accepted"
    assert appended_events[0]["data"]["response_preview"] == "继续执行"


@pytest.mark.asyncio
async def test_auth_interaction_callbacks_write_namespaced_audit_without_state_file(monkeypatch, temp_config_dirs):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    request_record = await store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None

    await _write_status(store, request_id, run_id, RunStatus.WAITING_AUTH)
    run_dir = (
        Path(request_record["workspace_dir"])
        if isinstance(request_record.get("workspace_dir"), str)
        else Path(config.SYSTEM.RUNS_DIR) / run_id
    )
    audit_dir = Path(request_record["input_manifest_path"]).parent
    state_path = run_dir / ".state" / audit_dir.name / "state.json"

    async def fake_select_auth_method(**kwargs):
        kwargs["append_orchestrator_event"](
            run_dir=run_dir,
            attempt_number=1,
            category="interaction",
            type_name="interaction.reply.accepted",
            data={
                "interaction_id": 1,
                "resolution_mode": "user_reply",
                "accepted_at": "2026-06-17T00:00:00+00:00",
                "response_preview": None,
            },
        )
        kwargs["update_status"](
            run_dir,
            RunStatus.WAITING_AUTH,
            error={"code": "AUTH_TEST_MARKER"},
        )
        return InteractionReplyResponse(
            request_id=request_id,
            status=RunStatus.WAITING_AUTH,
            accepted=True,
            mode="auth",
        )

    monkeypatch.setattr(
        interaction_service_module.run_auth_orchestration_service,
        "select_auth_method",
        fake_select_auth_method,
    )

    response = await jobs_router.reply_interaction(
        request_id,
        InteractionReplyRequest(
            interaction_id=1,
            mode="auth",
            response={},
            auth_session_id="auth-active",
            selection=AuthMethodSelection(value=AuthMethod.API_KEY),
        ),
        BackgroundTasks(),
    )

    assert response.accepted is True
    namespaced_events = audit_dir / "orchestrator_events.1.jsonl"
    assert namespaced_events.exists()
    assert not (run_dir / ".audit" / "orchestrator_events.1.jsonl").exists()
    assert not state_path.exists()


@pytest.mark.asyncio
async def test_reply_interaction_rejects_stale_interaction(monkeypatch, temp_config_dirs):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    request_record = await store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None

    await _write_status(store, request_id, run_id, RunStatus.WAITING_USER)
    await store.set_pending_interaction(
        request_id,
        {
            "interaction_id": 5,
            "kind": "open_text",
            "prompt": "Provide detail",
        },
    )

    with pytest.raises(HTTPException) as excinfo:
        await jobs_router.reply_interaction(
            request_id,
            InteractionReplyRequest(interaction_id=6, response={"detail": "x"}),
            BackgroundTasks(),
        )
    assert excinfo.value.status_code == 409
    assert "stale interaction" in str(excinfo.value.detail)


@pytest.mark.asyncio
async def test_interaction_endpoints_require_interactive_mode(monkeypatch, temp_config_dirs):
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)
    monkeypatch.setattr("server.runtime.observability.run_source_adapter.run_store", store)
    monkeypatch.setattr(
        jobs_router.model_registry,
        "validate_model",
        lambda _engine, model: {"model": model},
    )
    skill = _create_skill(temp_config_dirs, "demo-skill")
    _patch_skill_registry(monkeypatch, skill)

    response = await jobs_router.create_run(
        RunCreateRequest(
            skill_id=skill.id,
            engine="codex",
            parameter={},
            model="gpt-5.4-mini",
        ),
        BackgroundTasks(),
    )
    request_id = response.request_id

    pending = await jobs_router.get_interaction_pending(request_id)
    assert pending.status == RunStatus.QUEUED
    assert pending.effective_execution_mode == ExecutionMode.AUTO
    assert pending.pending is None
    assert pending.pending_auth is None
    assert pending.pending_auth_method_selection is None


@pytest.mark.asyncio
async def test_cancel_run_running_accepts(monkeypatch, temp_config_dirs):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    request_record = await store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None
    await _write_status(store, request_id, run_id, RunStatus.RUNNING)
    monkeypatch.setattr(
        jobs_router.job_orchestrator,
        "cancel_run",
        AsyncMock(return_value=True),
    )

    response = await jobs_router.cancel_run(request_id)
    assert response.request_id == request_id
    assert response.run_id == run_id
    assert response.accepted is True
    assert response.status == RunStatus.CANCELED


@pytest.mark.asyncio
async def test_cancel_run_terminal_is_idempotent(monkeypatch, temp_config_dirs):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    request_record = await store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None
    await _write_status(store, request_id, run_id, RunStatus.SUCCEEDED)
    cancel_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(jobs_router.job_orchestrator, "cancel_run", cancel_mock)

    response = await jobs_router.cancel_run(request_id)
    assert response.accepted is False
    assert response.status == RunStatus.SUCCEEDED
    cancel_mock.assert_not_called()
