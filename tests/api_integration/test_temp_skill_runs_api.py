import asyncio
import io
import json
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from server.config import config
from server.main import app
from server.models import RunStatus
from server.services.orchestration.job_orchestrator import job_orchestrator
from server.services.skill.temp_skill_run_manager import temp_skill_run_manager
from server.services.skill.temp_skill_run_store import temp_skill_run_store


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


async def _request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


async def _wait_status(request_id: str, timeout_sec: float = 5.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout_sec
    while asyncio.get_running_loop().time() < deadline:
        res = await _request("GET", f"/v1/temp-skill-runs/{request_id}")
        assert res.status_code == 200
        payload = res.json()
        if payload["status"] in ("succeeded", "failed", "canceled"):
            return payload
        await asyncio.sleep(0.05)
    raise AssertionError("Timed out waiting for terminal status")


@pytest.fixture(autouse=True)
def disable_lifespan_schedulers(monkeypatch):
    monkeypatch.setattr("server.services.platform.cache_manager.cache_manager.start", lambda: None)
    monkeypatch.setattr("server.services.platform.concurrency_manager.concurrency_manager.start", lambda: None)
    async def _admit():
        return True
    async def _acquire():
        return None
    async def _release():
        return None
    monkeypatch.setattr("server.services.platform.concurrency_manager.concurrency_manager.admit_or_reject", _admit)
    monkeypatch.setattr("server.services.platform.concurrency_manager.concurrency_manager.acquire_slot", _acquire)
    monkeypatch.setattr("server.services.platform.concurrency_manager.concurrency_manager.release_slot", _release)
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.run_cleanup_manager.start", lambda: None)
    monkeypatch.setattr("server.services.skill.temp_skill_cleanup_manager.temp_skill_cleanup_manager.start", lambda: None)


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

    async def _fake_run_job(
        *,
        run_id: str,
        temp_request_id: str | None = None,
        **_kwargs,
    ) -> None:
        assert temp_request_id
        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (run_dir / ".state").mkdir(parents=True, exist_ok=True)
        (run_dir / ".audit").mkdir(parents=True, exist_ok=True)
        (run_dir / "result").mkdir(parents=True, exist_ok=True)
        updated_at = "2026-02-16T00:00:00"
        (run_dir / "artifacts" / "out.txt").write_text("ok", encoding="utf-8")
        (run_dir / ".state" / "state.json").write_text(
            json.dumps(
                {
                    "request_id": temp_request_id,
                    "run_id": run_id,
                    "status": "succeeded",
                    "updated_at": updated_at,
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
                    "warnings": [],
                    "error": None,
                }
            ),
            encoding="utf-8",
        )
        (run_dir / ".audit" / "request_input.json").write_text("{}", encoding="utf-8")
        (run_dir / "result" / "result.json").write_text(
            json.dumps(
                {
                    "status": "success",
                    "data": {"message": "ok"},
                    "error": None,
                }
            ),
            encoding="utf-8",
        )
        await temp_skill_run_manager.on_terminal(temp_request_id, RunStatus.SUCCEEDED)

    monkeypatch.setattr("server.routers.temp_skill_runs.job_orchestrator.run_job", AsyncMock(side_effect=_fake_run_job))
    monkeypatch.setattr("server.routers.temp_skill_runs.run_store.get_request", AsyncMock(return_value=None))
    monkeypatch.setattr("server.routers.temp_skill_runs.run_store.create_request", AsyncMock(return_value=None))
    monkeypatch.setattr("server.routers.temp_skill_runs.run_store.update_request_manifest", AsyncMock(return_value=None))
    monkeypatch.setattr("server.routers.temp_skill_runs.run_store.update_request_cache_key", AsyncMock(return_value=None))
    monkeypatch.setattr("server.routers.temp_skill_runs.run_store.get_temp_cached_run", AsyncMock(return_value=None))
    monkeypatch.setattr("server.routers.temp_skill_runs.run_store.create_run", AsyncMock(return_value=None))
    monkeypatch.setattr("server.routers.temp_skill_runs.run_store.update_request_run_id", AsyncMock(return_value=None))
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.run_store.get_auto_decision_stats",
        AsyncMock(return_value={"auto_decision_count": 0, "last_auto_decision_at": None}),
    )
    monkeypatch.setattr("server.routers.temp_skill_runs.run_store.get_interaction_count", AsyncMock(return_value=0))
    monkeypatch.setattr("server.routers.temp_skill_runs.run_store.get_current_projection", AsyncMock(return_value=None))
    monkeypatch.setattr(
        "server.routers.temp_skill_runs.run_store.get_recovery_info",
        AsyncMock(
            return_value={
                "recovery_state": "none",
                "recovered_at": None,
                "recovery_reason": None,
            }
        ),
    )
    monkeypatch.setattr("server.routers.temp_skill_runs.run_store.get_pending_interaction", AsyncMock(return_value=None))
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


@pytest.mark.asyncio
async def test_temp_skill_two_step_run_and_cleanup(isolated_temp_env):
    create = await _request(
        "POST",
        "/v1/temp-skill-runs",
        json={"engine": "gemini", "parameter": {}, "runtime_options": {}},
    )
    assert create.status_code == 200
    request_id = create.json()["request_id"]

    upload = await _request(
        "POST",
        f"/v1/temp-skill-runs/{request_id}/upload",
        files={"skill_package": ("skill.zip", _build_skill_zip(), "application/zip")},
    )
    assert upload.status_code == 200

    status = await _wait_status(request_id)
    assert status["status"] == "succeeded"
    record = await temp_skill_run_store.get_request(request_id)
    assert record is not None
    run_id = record["run_id"]
    run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
    assert (run_dir / ".gemini" / "skills" / "demo-temp-api" / "SKILL.md").exists()

    result = await _request("GET", f"/v1/temp-skill-runs/{request_id}/result")
    assert result.status_code == 200
    assert result.json()["result"]["status"] == "success"
    assert result.json()["result"]["data"]["message"] == "ok"

    skills_lookup = await _request("GET", "/v1/skills/demo-temp-api")
    assert skills_lookup.status_code == 404

    temp_root = Path(config.SYSTEM.TEMP_SKILL_REQUESTS_DIR) / request_id
    assert (temp_root / "staged").exists() is False
    assert (temp_root / "skill_package.zip").exists() is False


@pytest.mark.asyncio
async def test_temp_skill_upload_validation_error(isolated_temp_env):
    create = await _request(
        "POST",
        "/v1/temp-skill-runs",
        json={"engine": "gemini", "parameter": {}, "runtime_options": {}},
    )
    assert create.status_code == 200
    request_id = create.json()["request_id"]

    upload = await _request(
        "POST",
        f"/v1/temp-skill-runs/{request_id}/upload",
        files={"skill_package": ("skill.zip", _build_bad_skill_zip(), "application/zip")},
    )
    assert upload.status_code == 400

    status = await _request("GET", f"/v1/temp-skill-runs/{request_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "failed"
