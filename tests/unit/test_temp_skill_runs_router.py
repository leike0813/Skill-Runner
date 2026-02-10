import io
import json
import zipfile
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from server.main import app
from server.models import RunStatus


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


@pytest.fixture(autouse=True)
def disable_schedulers(monkeypatch):
    monkeypatch.setattr("server.services.cache_manager.cache_manager.start", lambda: None)
    monkeypatch.setattr("server.services.run_cleanup_manager.run_cleanup_manager.start", lambda: None)
    monkeypatch.setattr("server.services.temp_skill_cleanup_manager.temp_skill_cleanup_manager.start", lambda: None)
    monkeypatch.setattr("server.services.concurrency_manager.concurrency_manager.start", lambda: None)


def test_create_temp_skill_run(temp_config_dirs, monkeypatch):
    monkeypatch.setattr("server.routers.temp_skill_runs.model_registry.validate_model", lambda _e, m: {"model": m})
    client = TestClient(app)
    response = client.post(
        "/v1/temp-skill-runs",
        json={
            "engine": "gemini",
            "parameter": {"x": 1},
            "model": "gemini-test",
            "runtime_options": {"no_cache": True},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["request_id"]


def test_upload_queue_full_returns_429_and_marks_failed(temp_config_dirs, monkeypatch):
    monkeypatch.setattr("server.routers.temp_skill_runs.model_registry.validate_model", lambda _e, m: {"model": m})
    async def _reject():
        return False
    monkeypatch.setattr("server.routers.temp_skill_runs.concurrency_manager.admit_or_reject", _reject)
    client = TestClient(app)
    create = client.post(
        "/v1/temp-skill-runs",
        json={"engine": "gemini", "parameter": {}, "model": "gemini-test", "runtime_options": {}},
    )
    request_id = create.json()["request_id"]
    upload = client.post(
        f"/v1/temp-skill-runs/{request_id}/upload",
        files={"skill_package": ("skill.zip", _build_skill_zip(), "application/zip")},
    )
    assert upload.status_code == 429
    status = client.get(f"/v1/temp-skill-runs/{request_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "failed"


def test_upload_success_executes_and_cleans_temp_assets(temp_config_dirs, monkeypatch):
    monkeypatch.setattr("server.routers.temp_skill_runs.model_registry.validate_model", lambda _e, m: {"model": m})

    async def _fake_run_job(
        run_id,
        skill_id,
        engine_name,
        options,
        cache_key=None,
        skill_override=None,
        temp_request_id=None,
    ):
        from server.services.workspace_manager import workspace_manager
        from server.services.temp_skill_run_manager import temp_skill_run_manager
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
            json.dumps({"status": "succeeded", "warnings": [], "error": None, "updated_at": "2026-01-01T00:00:00"}),
            encoding="utf-8",
        )
        if temp_request_id:
            temp_skill_run_manager.on_terminal(temp_request_id, RunStatus.SUCCEEDED, debug_keep_temp=False)

    monkeypatch.setattr("server.routers.temp_skill_runs.job_orchestrator.run_job", _fake_run_job)
    client = TestClient(app)
    create = client.post(
        "/v1/temp-skill-runs",
        json={"engine": "gemini", "parameter": {}, "model": "gemini-test", "runtime_options": {}},
    )
    request_id = create.json()["request_id"]
    upload = client.post(
        f"/v1/temp-skill-runs/{request_id}/upload",
        files={"skill_package": ("skill.zip", _build_skill_zip(), "application/zip")},
    )
    assert upload.status_code == 200

    status = client.get(f"/v1/temp-skill-runs/{request_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "succeeded"

    result = client.get(f"/v1/temp-skill-runs/{request_id}/result")
    assert result.status_code == 200
    assert result.json()["result"]["data"]["message"] == "ok"

    from server.config import config
    temp_root = Path(config.SYSTEM.TEMP_SKILL_REQUESTS_DIR) / request_id
    assert (temp_root / "skill_package.zip").exists() is False
    assert (temp_root / "staged").exists() is False
