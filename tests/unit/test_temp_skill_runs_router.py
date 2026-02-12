import inspect
import io
import json
import zipfile
from pathlib import Path
from tempfile import SpooledTemporaryFile

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import BackgroundTasks, HTTPException, UploadFile

from server.models import RunStatus, TempSkillRunCreateRequest
from server.routers import temp_skill_runs as temp_skill_runs_router


def _build_skill_zip(skill_id: str = "temp-router-skill", engines: list[str] | None = None) -> bytes:
    runner = {
        "id": skill_id,
        "engines": engines or ["gemini"],
        "schemas": {
            "input": "assets/input.schema.json",
            "parameter": "assets/parameter.schema.json",
            "output": "assets/output.schema.json",
        },
        "artifacts": [{"role": "result", "pattern": "out.txt", "required": True}],
    }
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
    monkeypatch.setattr("server.services.cache_manager.cache_manager.start", lambda: None)
    monkeypatch.setattr("server.services.run_cleanup_manager.run_cleanup_manager.start", lambda: None)
    monkeypatch.setattr("server.services.temp_skill_cleanup_manager.temp_skill_cleanup_manager.start", lambda: None)
    monkeypatch.setattr("server.services.concurrency_manager.concurrency_manager.start", lambda: None)


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
        from server.services.temp_skill_run_manager import temp_skill_run_manager
        from server.services.workspace_manager import workspace_manager

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
