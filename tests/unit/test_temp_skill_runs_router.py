import inspect
import io
import json
import zipfile
from pathlib import Path
from tempfile import SpooledTemporaryFile
from unittest.mock import AsyncMock, MagicMock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import BackgroundTasks, HTTPException, UploadFile

from server.models import RunStatus, TempSkillRunCreateRequest
from server.routers import temp_skill_runs as temp_skill_runs_router


def _build_skill_zip(
    skill_id: str = "temp-router-skill",
    engines: list[str] | None = None,
    unsupported_engines: list[str] | None = None,
    include_engines: bool = True,
    execution_modes: list[str] | None = None,
) -> bytes:
    runner: dict[str, object] = {
        "id": skill_id,
        "execution_modes": execution_modes or ["auto", "interactive"],
        "schemas": {
            "input": "assets/input.schema.json",
            "parameter": "assets/parameter.schema.json",
            "output": "assets/output.schema.json",
        },
        "artifacts": [{"role": "result", "pattern": "out.txt", "required": True}],
    }
    if include_engines:
        runner["engines"] = engines or ["gemini"]
    if unsupported_engines:
        runner["unsupported_engines"] = unsupported_engines
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{skill_id}/SKILL.md", f"---\nname: {skill_id}\n---\n")
        zf.writestr(f"{skill_id}/assets/runner.json", json.dumps(runner))
        zf.writestr(f"{skill_id}/assets/input.schema.json", json.dumps({"type": "object", "properties": {}}))
        zf.writestr(f"{skill_id}/assets/parameter.schema.json", json.dumps({"type": "object", "properties": {}}))
        zf.writestr(
            f"{skill_id}/assets/output.schema.json",
            json.dumps({"type": "object", "properties": {"message": {"type": "string"}}}),
        )
    return bio.getvalue()


def _build_upload_file(filename: str, payload: bytes) -> UploadFile:
    file_obj = SpooledTemporaryFile()
    file_obj.write(payload)
    file_obj.seek(0)
    return UploadFile(filename=filename, file=file_obj)


async def _run_background_tasks(background_tasks: BackgroundTasks) -> None:
    for task in background_tasks.tasks:
        outcome = task.func(*task.args, **task.kwargs)
        if inspect.isawaitable(outcome):
            await outcome


@pytest.fixture(autouse=True)
def disable_schedulers(monkeypatch):
    monkeypatch.setattr("server.services.platform.cache_manager.cache_manager.start", lambda: None)
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.run_cleanup_manager.start", lambda: None)
    monkeypatch.setattr("server.services.skill.temp_skill_cleanup_manager.temp_skill_cleanup_manager.start", lambda: None)
    monkeypatch.setattr("server.services.platform.concurrency_manager.concurrency_manager.start", lambda: None)


@pytest.mark.asyncio
async def test_create_temp_skill_run(temp_config_dirs, monkeypatch):
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.model_registry.validate_model",
        lambda _e, m: {"model": m},
    )

    response = await temp_skill_runs_router.create_temp_skill_run(
        TempSkillRunCreateRequest(
            engine="gemini",
            parameter={"x": 1},
            model="gemini-test",
            runtime_options={"no_cache": True},
        )
    )
    assert response.status == "queued"
    assert response.request_id


@pytest.mark.asyncio
async def test_upload_queue_full_returns_429_and_marks_failed(temp_config_dirs, monkeypatch):
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.model_registry.validate_model",
        lambda _e, m: {"model": m},
    )

    async def _reject():
        return False

    monkeypatch.setattr("server.routers.temp_skill_runs.concurrency_manager.admit_or_reject", _reject)

    create = await temp_skill_runs_router.create_temp_skill_run(
        TempSkillRunCreateRequest(
            engine="gemini",
            parameter={},
            model="gemini-test",
            runtime_options={},
        )
    )

    with pytest.raises(HTTPException) as exc:
        await temp_skill_runs_router.upload_temp_skill_and_start(
            create.request_id,
            BackgroundTasks(),
            skill_package=_build_upload_file("skill.zip", _build_skill_zip()),
            file=None,
        )
    assert exc.value.status_code == 429

    status = await temp_skill_runs_router.get_temp_skill_run_status(create.request_id)
    assert status.status == RunStatus.FAILED


@pytest.mark.asyncio
async def test_temp_status_exposes_interactive_auto_reply_fields(temp_config_dirs, monkeypatch):
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.model_registry.validate_model",
        lambda _e, m: {"model": m},
    )
    create = await temp_skill_runs_router.create_temp_skill_run(
        TempSkillRunCreateRequest(
            engine="gemini",
            parameter={},
            model="gemini-test",
            runtime_options={
                "execution_mode": "interactive",
                "interactive_auto_reply": True,
                "interactive_reply_timeout_sec": 8,
            },
        )
    )

    status = await temp_skill_runs_router.get_temp_skill_run_status(create.request_id)
    assert status.interactive_auto_reply is True
    assert status.interactive_reply_timeout_sec == 8


@pytest.mark.asyncio
async def test_upload_rejects_interactive_when_skill_declares_auto_only(temp_config_dirs, monkeypatch):
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.model_registry.validate_model",
        lambda _e, m: {"model": m},
    )
    create = await temp_skill_runs_router.create_temp_skill_run(
        TempSkillRunCreateRequest(
            engine="gemini",
            parameter={},
            model="gemini-test",
            runtime_options={"execution_mode": "interactive"},
        )
    )
    with pytest.raises(HTTPException) as exc:
        await temp_skill_runs_router.upload_temp_skill_and_start(
            create.request_id,
            BackgroundTasks(),
            skill_package=_build_upload_file(
                "skill.zip", _build_skill_zip(execution_modes=["auto"])
            ),
            file=None,
        )
    assert exc.value.status_code == 400
    assert isinstance(exc.value.detail, dict)
    assert exc.value.detail["code"] == "SKILL_EXECUTION_MODE_UNSUPPORTED"


@pytest.mark.asyncio
async def test_upload_rejects_engine_denied_by_unsupported_engines(temp_config_dirs, monkeypatch):
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.model_registry.validate_model",
        lambda _e, m: {"model": m},
    )
    create = await temp_skill_runs_router.create_temp_skill_run(
        TempSkillRunCreateRequest(
            engine="gemini",
            parameter={},
            model="gemini-test",
            runtime_options={},
        )
    )
    with pytest.raises(HTTPException) as exc:
        await temp_skill_runs_router.upload_temp_skill_and_start(
            create.request_id,
            BackgroundTasks(),
            skill_package=_build_upload_file(
                "skill.zip",
                _build_skill_zip(
                    include_engines=False,
                    unsupported_engines=["gemini"],
                ),
            ),
            file=None,
        )
    assert exc.value.status_code == 400
    assert isinstance(exc.value.detail, dict)
    assert exc.value.detail["code"] == "SKILL_ENGINE_UNSUPPORTED"


@pytest.mark.asyncio
async def test_upload_accepts_missing_engines_defaults_to_all(temp_config_dirs, monkeypatch):
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.model_registry.validate_model",
        lambda _e, m: {"model": m},
    )
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.job_orchestrator.run_job",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.concurrency_manager.admit_or_reject",
        AsyncMock(return_value=True),
    )
    create = await temp_skill_runs_router.create_temp_skill_run(
        TempSkillRunCreateRequest(
            engine="gemini",
            parameter={},
            model="gemini-test",
            runtime_options={},
        )
    )

    res = await temp_skill_runs_router.upload_temp_skill_and_start(
        create.request_id,
        BackgroundTasks(),
        skill_package=_build_upload_file(
            "skill.zip",
            _build_skill_zip(include_engines=False),
        ),
        file=None,
    )
    assert res.status == RunStatus.QUEUED
    assert res.cache_hit is False


@pytest.mark.asyncio
async def test_upload_auto_mode_cache_hit(temp_config_dirs, monkeypatch):
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.model_registry.validate_model",
        lambda _e, m: {"model": m},
    )
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.run_store.get_temp_cached_run",
        lambda _key: "run-cached-temp-1",
    )
    run_job_mock = AsyncMock()
    monkeypatch.setattr("server.routers.temp_skill_runs.job_orchestrator.run_job", run_job_mock)

    create = await temp_skill_runs_router.create_temp_skill_run(
        TempSkillRunCreateRequest(
            engine="gemini",
            parameter={},
            model="gemini-test",
            runtime_options={"execution_mode": "auto"},
        )
    )

    res = await temp_skill_runs_router.upload_temp_skill_and_start(
        create.request_id,
        BackgroundTasks(),
        skill_package=_build_upload_file("skill.zip", _build_skill_zip()),
        file=None,
    )
    assert res.status == RunStatus.SUCCEEDED
    assert res.cache_hit is True
    run_job_mock.assert_not_called()

    record = temp_skill_runs_router.temp_skill_run_store.get_request(create.request_id)
    assert record is not None
    assert record.get("run_id") == "run-cached-temp-1"

    from server.config import config

    temp_root = Path(config.SYSTEM.TEMP_SKILL_REQUESTS_DIR) / create.request_id
    assert (temp_root / "skill_package.zip").exists() is False
    assert (temp_root / "staged").exists() is False


@pytest.mark.asyncio
async def test_upload_interactive_mode_skips_cache_lookup_and_writeback_key(temp_config_dirs, monkeypatch):
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.model_registry.validate_model",
        lambda _e, m: {"model": m},
    )
    get_cached_run_mock = MagicMock(return_value="run-cached-temp-2")
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.run_store.get_temp_cached_run",
        get_cached_run_mock,
    )
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.concurrency_manager.admit_or_reject",
        AsyncMock(return_value=True),
    )
    run_job_mock = AsyncMock()
    monkeypatch.setattr("server.routers.temp_skill_runs.job_orchestrator.run_job", run_job_mock)

    create = await temp_skill_runs_router.create_temp_skill_run(
        TempSkillRunCreateRequest(
            engine="gemini",
            parameter={},
            model="gemini-test",
            runtime_options={"execution_mode": "interactive"},
        )
    )

    background_tasks = BackgroundTasks()
    res = await temp_skill_runs_router.upload_temp_skill_and_start(
        create.request_id,
        background_tasks,
        skill_package=_build_upload_file("skill.zip", _build_skill_zip()),
        file=None,
    )
    assert res.status == RunStatus.QUEUED
    assert res.cache_hit is False
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].kwargs["cache_key"] is None
    get_cached_run_mock.assert_not_called()


@pytest.mark.asyncio
async def test_upload_auto_mode_no_cache_skips_lookup_and_writeback_key(temp_config_dirs, monkeypatch):
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.model_registry.validate_model",
        lambda _e, m: {"model": m},
    )
    get_cached_run_mock = MagicMock(return_value="run-cached-temp-3")
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.run_store.get_temp_cached_run",
        get_cached_run_mock,
    )
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.concurrency_manager.admit_or_reject",
        AsyncMock(return_value=True),
    )
    run_job_mock = AsyncMock()
    monkeypatch.setattr("server.routers.temp_skill_runs.job_orchestrator.run_job", run_job_mock)

    create = await temp_skill_runs_router.create_temp_skill_run(
        TempSkillRunCreateRequest(
            engine="gemini",
            parameter={},
            model="gemini-test",
            runtime_options={"execution_mode": "auto", "no_cache": True},
        )
    )

    background_tasks = BackgroundTasks()
    res = await temp_skill_runs_router.upload_temp_skill_and_start(
        create.request_id,
        background_tasks,
        skill_package=_build_upload_file("skill.zip", _build_skill_zip()),
        file=None,
    )
    assert res.status == RunStatus.QUEUED
    assert res.cache_hit is False
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].kwargs["cache_key"] is None
    get_cached_run_mock.assert_not_called()


@pytest.mark.asyncio
async def test_upload_success_executes_and_cleans_temp_assets(temp_config_dirs, monkeypatch):
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.model_registry.validate_model",
        lambda _e, m: {"model": m},
    )

    async def _fake_run_job(
        run_id,
        skill_id,
        engine_name,
        options,
        cache_key=None,
        skill_override=None,
        temp_request_id=None,
    ):
        from server.services.skill.temp_skill_run_manager import temp_skill_run_manager
        from server.services.orchestration.workspace_manager import workspace_manager

        run_dir = workspace_manager.get_run_dir(run_id)
        assert run_dir is not None
        (run_dir / "artifacts" / "out.txt").write_text("ok", encoding="utf-8")
        payload = {
            "status": "success",
            "data": {"message": "ok"},
            "artifacts": ["artifacts/out.txt"],
            "validation_warnings": [],
            "error": None,
        }
        (run_dir / "result" / "result.json").write_text(json.dumps(payload), encoding="utf-8")
        (run_dir / "status.json").write_text(
            json.dumps(
                {
                    "status": "succeeded",
                    "warnings": [],
                    "error": None,
                    "updated_at": "2026-01-01T00:00:00",
                }
            ),
            encoding="utf-8",
        )
        if temp_request_id:
            temp_skill_run_manager.on_terminal(temp_request_id, RunStatus.SUCCEEDED, debug_keep_temp=False)

    monkeypatch.setattr("server.routers.temp_skill_runs.job_orchestrator.run_job", _fake_run_job)

    create = await temp_skill_runs_router.create_temp_skill_run(
        TempSkillRunCreateRequest(
            engine="gemini",
            parameter={},
            model="gemini-test",
            runtime_options={},
        )
    )

    background_tasks = BackgroundTasks()
    upload = await temp_skill_runs_router.upload_temp_skill_and_start(
        create.request_id,
        background_tasks,
        skill_package=_build_upload_file("skill.zip", _build_skill_zip()),
        file=None,
    )
    assert upload.status == RunStatus.QUEUED
    await _run_background_tasks(background_tasks)

    status = await temp_skill_runs_router.get_temp_skill_run_status(create.request_id)
    assert status.status == RunStatus.SUCCEEDED

    result = await temp_skill_runs_router.get_temp_skill_run_result(create.request_id)
    assert result.result["data"]["message"] == "ok"

    from server.config import config

    temp_root = Path(config.SYSTEM.TEMP_SKILL_REQUESTS_DIR) / create.request_id
    assert (temp_root / "skill_package.zip").exists() is False
    assert (temp_root / "staged").exists() is False


@pytest.mark.asyncio
async def test_cancel_temp_skill_run_active_accepts(temp_config_dirs, monkeypatch):
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.model_registry.validate_model",
        lambda _e, m: {"model": m},
    )
    create = await temp_skill_runs_router.create_temp_skill_run(
        TempSkillRunCreateRequest(
            engine="gemini",
            parameter={},
            model="gemini-test",
            runtime_options={},
        )
    )
    temp_skill_runs_router.temp_skill_run_store.update_run_started(create.request_id, "run-temp-1")
    run_dir = Path(temp_config_dirs / "runs" / "run-temp-1")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(
        json.dumps({"status": "running", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        temp_skill_runs_router.workspace_manager,
        "get_run_dir",
        lambda run_id: run_dir if run_id == "run-temp-1" else None,
    )
    cancel_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(temp_skill_runs_router.job_orchestrator, "cancel_run", cancel_mock)

    response = await temp_skill_runs_router.cancel_temp_skill_run(create.request_id)
    assert response.request_id == create.request_id
    assert response.run_id == "run-temp-1"
    assert response.status == RunStatus.CANCELED
    assert response.accepted is True


@pytest.mark.asyncio
async def test_cancel_temp_skill_run_terminal_idempotent(temp_config_dirs, monkeypatch):
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.model_registry.validate_model",
        lambda _e, m: {"model": m},
    )
    create = await temp_skill_runs_router.create_temp_skill_run(
        TempSkillRunCreateRequest(
            engine="gemini",
            parameter={},
            model="gemini-test",
            runtime_options={},
        )
    )
    temp_skill_runs_router.temp_skill_run_store.update_run_started(create.request_id, "run-temp-2")
    run_dir = Path(temp_config_dirs / "runs" / "run-temp-2")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(
        json.dumps({"status": "succeeded", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        temp_skill_runs_router.workspace_manager,
        "get_run_dir",
        lambda run_id: run_dir if run_id == "run-temp-2" else None,
    )
    cancel_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(temp_skill_runs_router.job_orchestrator, "cancel_run", cancel_mock)

    response = await temp_skill_runs_router.cancel_temp_skill_run(create.request_id)
    assert response.accepted is False
    assert response.status == RunStatus.SUCCEEDED
    cancel_mock.assert_not_called()


@pytest.mark.asyncio
async def test_upload_syncs_temp_request_into_run_store(temp_config_dirs, monkeypatch):
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.model_registry.validate_model",
        lambda _e, m: {"model": m},
    )
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.concurrency_manager.admit_or_reject",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.job_orchestrator.run_job",
        AsyncMock(),
    )

    create = await temp_skill_runs_router.create_temp_skill_run(
        TempSkillRunCreateRequest(
            engine="gemini",
            parameter={"k": "v"},
            model="gemini-test",
            runtime_options={"execution_mode": "interactive"},
        )
    )
    upload = await temp_skill_runs_router.upload_temp_skill_and_start(
        create.request_id,
        BackgroundTasks(),
        skill_package=_build_upload_file("skill.zip", _build_skill_zip()),
        file=None,
    )
    assert upload.status == RunStatus.QUEUED

    regular_record = temp_skill_runs_router.run_store.get_request(create.request_id)
    assert regular_record is not None
    assert regular_record["request_id"] == create.request_id
    assert regular_record["skill_id"] == "temp-router-skill"
    assert regular_record["run_id"]


@pytest.mark.asyncio
async def test_temp_interaction_pending_and_reply_parity(temp_config_dirs, monkeypatch):
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.model_registry.validate_model",
        lambda _e, m: {"model": m},
    )
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.concurrency_manager.admit_or_reject",
        AsyncMock(return_value=True),
    )
    run_job_mock = AsyncMock()
    monkeypatch.setattr("server.routers.temp_skill_runs.job_orchestrator.run_job", run_job_mock)

    create = await temp_skill_runs_router.create_temp_skill_run(
        TempSkillRunCreateRequest(
            engine="gemini",
            parameter={},
            model="gemini-test",
            runtime_options={"execution_mode": "interactive"},
        )
    )
    await temp_skill_runs_router.upload_temp_skill_and_start(
        create.request_id,
        BackgroundTasks(),
        skill_package=_build_upload_file("skill.zip", _build_skill_zip()),
        file=None,
    )
    rec = temp_skill_runs_router.temp_skill_run_store.get_request(create.request_id)
    assert rec is not None
    run_id = rec["run_id"]
    assert isinstance(run_id, str)

    run_dir = Path(temp_config_dirs / "runs" / run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(
        json.dumps({"status": "waiting_user", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        temp_skill_runs_router.workspace_manager,
        "get_run_dir",
        lambda candidate: run_dir if candidate == run_id else None,
    )

    temp_skill_runs_router.run_store.set_pending_interaction(
        create.request_id,
        {
            "interaction_id": 3,
            "kind": "open_text",
            "prompt": "Need input",
            "options": [],
            "ui_hints": {},
            "default_decision_policy": "engine_judgement",
            "required_fields": [],
        },
    )

    pending = await temp_skill_runs_router.get_temp_skill_interaction_pending(create.request_id)
    assert pending.status == RunStatus.WAITING_USER
    assert pending.pending is not None
    assert pending.pending.interaction_id == 3

    background_tasks = BackgroundTasks()
    reply = await temp_skill_runs_router.reply_temp_skill_interaction(
        create.request_id,
        request=temp_skill_runs_router.InteractionReplyRequest(
            interaction_id=3,
            response={"answer": "ok"},
            idempotency_key="ik-1",
        ),
        background_tasks=background_tasks,
    )
    assert reply.accepted is True
    assert reply.status == RunStatus.QUEUED
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].kwargs["temp_request_id"] == create.request_id
