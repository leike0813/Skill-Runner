import io
import json
import time
import zipfile
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from server.config import config
from server.main import app
from server.services.job_orchestrator import job_orchestrator


def _build_skill_zip(skill_id: str = "demo-temp-api") -> bytes:
    runner = {
        "id": skill_id,
        "engines": ["gemini"],
        "execution_modes": ["auto", "interactive"],
        "schemas": {
            "input": "assets/input.schema.json",
            "parameter": "assets/parameter.schema.json",
            "output": "assets/output.schema.json",
        },
        "artifacts": [{"role": "result", "pattern": "out.txt", "required": True}],
    }
    output_schema = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
    }
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{skill_id}/SKILL.md", f"---\nname: {skill_id}\n---\n")
        zf.writestr(f"{skill_id}/assets/runner.json", json.dumps(runner))
        zf.writestr(f"{skill_id}/assets/input.schema.json", json.dumps({"type": "object", "properties": {}}))
        zf.writestr(f"{skill_id}/assets/parameter.schema.json", json.dumps({"type": "object", "properties": {}}))
        zf.writestr(f"{skill_id}/assets/output.schema.json", json.dumps(output_schema))
    return bio.getvalue()


def _build_bad_skill_zip(skill_id: str = "demo-temp-bad") -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{skill_id}/SKILL.md", f"---\nname: {skill_id}\n---\n")
    return bio.getvalue()


def _wait_status(client: TestClient, request_id: str, timeout_sec: float = 5.0) -> dict:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        res = client.get(f"/v1/temp-skill-runs/{request_id}")
        assert res.status_code == 200
        payload = res.json()
        if payload["status"] in ("succeeded", "failed", "canceled"):
            return payload
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for terminal status")


@pytest.fixture(autouse=True)
def disable_lifespan_schedulers(monkeypatch):
    monkeypatch.setattr("server.services.cache_manager.cache_manager.start", lambda: None)
    monkeypatch.setattr("server.services.concurrency_manager.concurrency_manager.start", lambda: None)
    async def _admit():
        return True
    async def _acquire():
        return None
    async def _release():
        return None
    monkeypatch.setattr("server.services.concurrency_manager.concurrency_manager.admit_or_reject", _admit)
    monkeypatch.setattr("server.services.concurrency_manager.concurrency_manager.acquire_slot", _acquire)
    monkeypatch.setattr("server.services.concurrency_manager.concurrency_manager.release_slot", _release)
    monkeypatch.setattr("server.services.run_cleanup_manager.run_cleanup_manager.start", lambda: None)
    monkeypatch.setattr("server.services.temp_skill_cleanup_manager.temp_skill_cleanup_manager.start", lambda: None)


@pytest.fixture
def isolated_temp_env(monkeypatch, tmp_path):
    old_data_dir = config.SYSTEM.DATA_DIR
    old_runs_dir = config.SYSTEM.RUNS_DIR
    old_requests_dir = config.SYSTEM.REQUESTS_DIR
    old_temp_db = config.SYSTEM.TEMP_SKILL_RUNS_DB
    old_temp_req = config.SYSTEM.TEMP_SKILL_REQUESTS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    old_installs_db = config.SYSTEM.SKILL_INSTALLS_DB
    old_installs_dir = config.SYSTEM.SKILL_INSTALLS_DIR
    old_archive = config.SYSTEM.SKILLS_ARCHIVE_DIR
    old_staging = config.SYSTEM.SKILLS_STAGING_DIR

    config.defrost()
    config.SYSTEM.DATA_DIR = str(tmp_path / "data")
    config.SYSTEM.RUNS_DIR = str(tmp_path / "data" / "runs")
    config.SYSTEM.REQUESTS_DIR = str(tmp_path / "data" / "requests")
    config.SYSTEM.RUNS_DB = str(tmp_path / "data" / "runs.db")
    config.SYSTEM.SKILL_INSTALLS_DB = str(tmp_path / "data" / "skill_installs.db")
    config.SYSTEM.SKILL_INSTALLS_DIR = str(tmp_path / "data" / "skill_installs")
    config.SYSTEM.SKILLS_ARCHIVE_DIR = str(tmp_path / "skills" / ".archive")
    config.SYSTEM.SKILLS_STAGING_DIR = str(tmp_path / "skills" / ".staging")
    config.SYSTEM.TEMP_SKILL_RUNS_DB = str(tmp_path / "data" / "temp_skill_runs.db")
    config.SYSTEM.TEMP_SKILL_REQUESTS_DIR = str(tmp_path / "data" / "temp_skill_runs" / "requests")
    config.freeze()

    for p in (
        Path(config.SYSTEM.RUNS_DIR),
        Path(config.SYSTEM.REQUESTS_DIR),
        Path(config.SYSTEM.TEMP_SKILL_REQUESTS_DIR),
    ):
        p.mkdir(parents=True, exist_ok=True)

    class _FakeAdapter:
        async def run(self, skill, input_data, run_dir, options):
            from server.adapters.base import EngineRunResult

            (run_dir / "artifacts" / "out.txt").write_text("ok", encoding="utf-8")
            result_path = run_dir / "result" / "result.json"
            result_path.write_text(json.dumps({"message": "ok"}), encoding="utf-8")
            return EngineRunResult(
                exit_code=0,
                raw_stdout='{"message":"ok"}',
                raw_stderr="",
                output_file_path=result_path,
                artifacts_created=[run_dir / "artifacts" / "out.txt"],
            )

    monkeypatch.setitem(job_orchestrator.adapters, "gemini", _FakeAdapter())
    try:
        yield tmp_path
    finally:
        config.defrost()
        config.SYSTEM.DATA_DIR = old_data_dir
        config.SYSTEM.RUNS_DIR = old_runs_dir
        config.SYSTEM.REQUESTS_DIR = old_requests_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.SYSTEM.SKILL_INSTALLS_DB = old_installs_db
        config.SYSTEM.SKILL_INSTALLS_DIR = old_installs_dir
        config.SYSTEM.SKILLS_ARCHIVE_DIR = old_archive
        config.SYSTEM.SKILLS_STAGING_DIR = old_staging
        config.SYSTEM.TEMP_SKILL_RUNS_DB = old_temp_db
        config.SYSTEM.TEMP_SKILL_REQUESTS_DIR = old_temp_req
        config.freeze()


def test_temp_skill_two_step_run_and_cleanup(isolated_temp_env):
    with TestClient(app) as client:
        create = client.post(
            "/v1/temp-skill-runs",
            json={"engine": "gemini", "parameter": {}, "runtime_options": {}},
        )
        assert create.status_code == 200
        request_id = create.json()["request_id"]

        upload = client.post(
            f"/v1/temp-skill-runs/{request_id}/upload",
            files={"skill_package": ("skill.zip", _build_skill_zip(), "application/zip")},
        )
        assert upload.status_code == 200

        status = _wait_status(client, request_id)
        assert status["status"] == "succeeded"

        result = client.get(f"/v1/temp-skill-runs/{request_id}/result")
        assert result.status_code == 200
        assert result.json()["result"]["status"] == "success"
        assert result.json()["result"]["data"]["message"] == "ok"

        skills_lookup = client.get("/v1/skills/demo-temp-api")
        assert skills_lookup.status_code == 404

        temp_root = Path(config.SYSTEM.TEMP_SKILL_REQUESTS_DIR) / request_id
        assert (temp_root / "staged").exists() is False
        assert (temp_root / "skill_package.zip").exists() is False


def test_temp_skill_upload_validation_error(isolated_temp_env):
    with TestClient(app) as client:
        create = client.post(
            "/v1/temp-skill-runs",
            json={"engine": "gemini", "parameter": {}, "runtime_options": {}},
        )
        assert create.status_code == 200
        request_id = create.json()["request_id"]

        upload = client.post(
            f"/v1/temp-skill-runs/{request_id}/upload",
            files={"skill_package": ("skill.zip", _build_bad_skill_zip(), "application/zip")},
        )
        assert upload.status_code == 400

        status = client.get(f"/v1/temp-skill-runs/{request_id}")
        assert status.status_code == 200
        assert status.json()["status"] == "failed"
