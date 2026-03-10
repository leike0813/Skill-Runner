import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import BackgroundTasks, HTTPException

from server.config import config
from server.models import ExecutionMode, InteractionReplyRequest, RunCreateRequest, RunStatus, SkillManifest
from server.routers import jobs as jobs_router
from server.services.orchestration.run_store import RunStore


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
                "engines": ["gemini"],
                "execution_modes": modes,
            }
        ),
        encoding="utf-8",
    )
    return SkillManifest(
        id=skill_id,
        path=skill_dir,
        engines=["gemini"],
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
    run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
    state_dir = run_dir / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)
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
    (state_dir / "state.json").write_text(json.dumps(payload), encoding="utf-8")
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
            engine="gemini",
            parameter={},
            model="gemini-2.5-pro",
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
            engine="gemini",
            parameter={},
            model="gemini-2.5-pro",
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
            engine="gemini",
            parameter={},
            model="gemini-2.5-pro",
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
        jobs_router.job_orchestrator,
        "_append_orchestrator_event",
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
        jobs_router.job_orchestrator,
        "_append_orchestrator_event",
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
            engine="gemini",
            parameter={},
            model="gemini-2.5-pro",
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
