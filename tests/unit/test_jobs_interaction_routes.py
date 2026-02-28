import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import BackgroundTasks, HTTPException

from server.config import config
from server.models import InteractionReplyRequest, RunCreateRequest, RunStatus, SkillManifest
from server.routers import jobs as jobs_router
from server.services.orchestration.run_store import RunStore


def _create_skill(base_dir: Path, skill_id: str) -> SkillManifest:
    skill_dir = base_dir / skill_id
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("skill", encoding="utf-8")
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": skill_id,
                "engines": ["gemini"],
                "execution_modes": ["auto", "interactive"],
            }
        ),
        encoding="utf-8",
    )
    return SkillManifest(
        id=skill_id,
        path=skill_dir,
        engines=["gemini"],
        execution_modes=["auto", "interactive"],
    )


def _patch_skill_registry(monkeypatch: pytest.MonkeyPatch, skill: SkillManifest) -> None:
    monkeypatch.setattr(
        jobs_router.skill_registry,
        "get_skill",
        lambda skill_id: skill if skill_id == skill.id else None,
    )


def _write_status(run_id: str, status: RunStatus) -> None:
    run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
    payload = {
        "status": status.value,
        "updated_at": "2026-02-16T00:00:00",
        "warnings": [],
        "error": None,
    }
    (run_dir / "status.json").write_text(json.dumps(payload), encoding="utf-8")


async def _create_interactive_request(
    monkeypatch: pytest.MonkeyPatch,
    temp_config_dirs: Path,
    *,
    runtime_options: dict[str, object] | None = None,
) -> tuple[RunStore, str]:
    store = RunStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr(jobs_router, "run_store", store)
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
    request_record = store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None

    _write_status(run_id, RunStatus.WAITING_USER)
    store.set_pending_interaction(
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
    request_record = store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None

    _write_status(run_id, RunStatus.WAITING_USER)
    store.set_pending_interaction(
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
    request_record = store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None

    _write_status(run_id, RunStatus.WAITING_USER)
    response = await jobs_router.get_run_status(request_id)
    assert response.status == RunStatus.WAITING_USER
    assert response.interactive_auto_reply is True
    assert response.interactive_reply_timeout_sec == 5


@pytest.mark.asyncio
async def test_reply_interaction_accepts_and_transitions_to_queued(monkeypatch, temp_config_dirs):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    monkeypatch.setattr(jobs_router.concurrency_manager, "admit_or_reject", AsyncMock(return_value=True))
    request_record = store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None

    _write_status(run_id, RunStatus.WAITING_USER)
    store.set_pending_interaction(
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind",
    ["choose_one", "confirm", "fill_fields", "open_text", "risk_ack"],
)
async def test_reply_interaction_accepts_free_text_for_all_supported_kinds(
    monkeypatch,
    temp_config_dirs,
    kind: str,
):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    monkeypatch.setattr(jobs_router.concurrency_manager, "admit_or_reject", AsyncMock(return_value=True))
    request_record = store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None

    _write_status(run_id, RunStatus.WAITING_USER)
    store.set_pending_interaction(
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
async def test_reply_interaction_rejects_stale_interaction(monkeypatch, temp_config_dirs):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    request_record = store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None

    _write_status(run_id, RunStatus.WAITING_USER)
    store.set_pending_interaction(
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

    with pytest.raises(HTTPException) as excinfo:
        await jobs_router.get_interaction_pending(request_id)
    assert excinfo.value.status_code == 400
    assert "execution_mode=interactive" in str(excinfo.value.detail)


@pytest.mark.asyncio
async def test_cancel_run_running_accepts(monkeypatch, temp_config_dirs):
    store, request_id = await _create_interactive_request(monkeypatch, temp_config_dirs)
    request_record = store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None
    _write_status(run_id, RunStatus.RUNNING)
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
    request_record = store.get_request(request_id)
    assert request_record is not None
    run_id = request_record["run_id"]
    assert run_id is not None
    _write_status(run_id, RunStatus.SUCCEEDED)
    cancel_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(jobs_router.job_orchestrator, "cancel_run", cancel_mock)

    response = await jobs_router.cancel_run(request_id)
    assert response.accepted is False
    assert response.status == RunStatus.SUCCEEDED
    cancel_mock.assert_not_called()
