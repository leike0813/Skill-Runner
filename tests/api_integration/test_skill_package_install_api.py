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
from server.services.skill.skill_install_store import SkillInstallStore


def _build_skill_zip(skill_id: str, version: str) -> bytes:
    runner = {
        "id": skill_id,
        "version": version,
        "engines": ["gemini"],
        "execution_modes": ["auto", "interactive"],
        "schemas": {
            "input": "assets/input.schema.json",
            "parameter": "assets/parameter.schema.json",
            "output": "assets/output.schema.json"
        },
        "artifacts": [
            {
                "role": "summary",
                "pattern": "artifacts/summary.md",
                "required": True
            }
        ]
    }
    skill_md = (
        "---\n"
        f"name: {skill_id}\n"
        "description: uploaded skill\n"
        "---\n\n"
        "# Uploaded Skill\n"
    )
    input_schema = {"type": "object", "properties": {}}
    parameter_schema = {"type": "object", "properties": {}}
    output_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "x-type": "artifact"}
        },
        "required": ["summary"]
    }

    buff = io.BytesIO()
    with zipfile.ZipFile(buff, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{skill_id}/SKILL.md", skill_md)
        zf.writestr(f"{skill_id}/assets/runner.json", json.dumps(runner))
        zf.writestr(f"{skill_id}/assets/input.schema.json", json.dumps(input_schema))
        zf.writestr(f"{skill_id}/assets/parameter.schema.json", json.dumps(parameter_schema))
        zf.writestr(f"{skill_id}/assets/output.schema.json", json.dumps(output_schema))
    return buff.getvalue()


def _build_invalid_zip_missing_output_schema(skill_id: str, version: str) -> bytes:
    runner = {
        "id": skill_id,
        "version": version,
        "engines": ["gemini"],
        "execution_modes": ["auto", "interactive"],
        "schemas": {
            "input": "assets/input.schema.json",
            "parameter": "assets/parameter.schema.json",
            "output": "assets/output.schema.json"
        },
        "artifacts": [{"role": "summary", "pattern": "artifacts/summary.md", "required": True}]
    }
    buff = io.BytesIO()
    with zipfile.ZipFile(buff, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{skill_id}/SKILL.md", f"---\nname: {skill_id}\n---\n")
        zf.writestr(f"{skill_id}/assets/runner.json", json.dumps(runner))
        zf.writestr(f"{skill_id}/assets/input.schema.json", json.dumps({"type": "object"}))
        zf.writestr(f"{skill_id}/assets/parameter.schema.json", json.dumps({"type": "object"}))
    return buff.getvalue()


async def _request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


async def _wait_install_status(request_id: str, timeout_sec: float = 5.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout_sec
    while asyncio.get_running_loop().time() < deadline:
        res = await _request("GET", f"/v1/skill-packages/{request_id}")
        assert res.status_code == 200
        payload = res.json()
        if payload["status"] in ("succeeded", "failed"):
            return payload
        await asyncio.sleep(0.05)
    raise AssertionError(f"Timed out waiting for install status: {request_id}")


@pytest.fixture
def isolated_skill_install_env(monkeypatch, tmp_path):
    old_skills_dir = config.SYSTEM.SKILLS_DIR
    old_archive_dir = config.SYSTEM.SKILLS_ARCHIVE_DIR
    old_staging_dir = config.SYSTEM.SKILLS_STAGING_DIR
    old_install_dir = config.SYSTEM.SKILL_INSTALLS_DIR
    old_runs_db = config.SYSTEM.RUNS_DB
    old_install_db = config.SYSTEM.SKILL_INSTALLS_DB

    config.defrost()
    config.SYSTEM.SKILLS_DIR = str(tmp_path / "skills")
    config.SYSTEM.SKILLS_ARCHIVE_DIR = str(tmp_path / "skills" / ".archive")
    config.SYSTEM.SKILLS_STAGING_DIR = str(tmp_path / "skills" / ".staging")
    config.SYSTEM.SKILL_INSTALLS_DIR = str(tmp_path / "skill_installs")
    config.SYSTEM.RUNS_DB = str(tmp_path / "runs.db")
    config.SYSTEM.SKILL_INSTALLS_DB = config.SYSTEM.RUNS_DB
    config.freeze()

    store = SkillInstallStore(db_path=Path(config.SYSTEM.RUNS_DB))
    monkeypatch.setattr("server.routers.skill_packages.skill_install_store", store)
    monkeypatch.setattr("server.services.skill.skill_package_manager.skill_install_store", store)
    try:
        yield tmp_path
    finally:
        config.defrost()
        config.SYSTEM.SKILLS_DIR = old_skills_dir
        config.SYSTEM.SKILLS_ARCHIVE_DIR = old_archive_dir
        config.SYSTEM.SKILLS_STAGING_DIR = old_staging_dir
        config.SYSTEM.SKILL_INSTALLS_DIR = old_install_dir
        config.SYSTEM.RUNS_DB = old_runs_db
        config.SYSTEM.SKILL_INSTALLS_DB = old_install_db
        config.freeze()


@pytest.fixture(autouse=True)
def disable_lifespan_schedulers(monkeypatch):
    monkeypatch.setattr("server.services.platform.cache_manager.cache_manager.start", lambda: None)
    monkeypatch.setattr("server.services.platform.concurrency_manager.concurrency_manager.start", lambda: None)
    monkeypatch.setattr("server.services.orchestration.run_cleanup_manager.run_cleanup_manager.start", lambda: None)
    monkeypatch.setattr(
        "server.services.engine_management.engine_status_cache_service.engine_status_cache_service.refresh_all",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "server.services.engine_management.engine_status_cache_service.engine_status_cache_service.start",
        lambda: None,
    )
    monkeypatch.setattr(
        "server.services.engine_management.engine_status_cache_service.engine_status_cache_service.stop",
        lambda: None,
    )
    monkeypatch.setattr(
        "server.engines.opencode.models.catalog_service.opencode_model_catalog.start",
        lambda: None,
    )
    monkeypatch.setattr(
        "server.engines.opencode.models.catalog_service.opencode_model_catalog.refresh",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "server.engines.opencode.models.catalog_service.opencode_model_catalog.stop",
        lambda: None,
    )
    monkeypatch.setattr(
        "server.runtime.auth_detection.service.auth_detection_service.preload",
        lambda: None,
    )
    monkeypatch.setattr(
        "server.services.orchestration.job_orchestrator.job_orchestrator.recover_incomplete_runs_on_startup",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr("server.services.platform.process_supervisor.process_supervisor.start", lambda: None)
    monkeypatch.setattr(
        "server.services.platform.process_supervisor.process_supervisor.reap_orphan_leases_on_startup",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "server.services.platform.process_supervisor.process_supervisor.stop",
        AsyncMock(return_value=None),
    )


@pytest.mark.asyncio
async def test_install_new_skill_and_discoverable(isolated_skill_install_env):
    skill_id = "demo-upload-int"
    upload = _build_skill_zip(skill_id, "1.0.0")
    res = await _request(
        "POST",
        "/v1/skill-packages/install",
        files={"file": ("skill.zip", upload, "application/zip")}
    )
    assert res.status_code == 200
    request_id = res.json()["request_id"]

    status = await _wait_install_status(request_id)
    assert status["status"] == "succeeded"
    assert status["skill_id"] == skill_id
    assert status["version"] == "1.0.0"
    assert status["action"] == "install"

    skill_res = await _request("GET", f"/v1/skills/{skill_id}")
    assert skill_res.status_code == 200
    assert skill_res.json()["id"] == skill_id


@pytest.mark.asyncio
async def test_update_archives_previous_version(isolated_skill_install_env):
    skill_id = "demo-upload-int"
    v1 = _build_skill_zip(skill_id, "1.0.0")
    r1 = await _request("POST", "/v1/skill-packages/install", files={"file": ("v1.zip", v1, "application/zip")})
    assert r1.status_code == 200
    s1 = await _wait_install_status(r1.json()["request_id"])
    assert s1["status"] == "succeeded"

    v2 = _build_skill_zip(skill_id, "1.1.0")
    r2 = await _request("POST", "/v1/skill-packages/install", files={"file": ("v2.zip", v2, "application/zip")})
    assert r2.status_code == 200
    s2 = await _wait_install_status(r2.json()["request_id"])
    assert s2["status"] == "succeeded"
    assert s2["action"] == "update"

    archived_runner = Path(config.SYSTEM.SKILLS_ARCHIVE_DIR) / skill_id / "1.0.0" / "assets" / "runner.json"
    assert archived_runner.exists()


@pytest.mark.asyncio
async def test_reject_downgrade_update(isolated_skill_install_env):
    skill_id = "demo-upload-int"
    v2 = _build_skill_zip(skill_id, "2.0.0")
    r1 = await _request("POST", "/v1/skill-packages/install", files={"file": ("v2.zip", v2, "application/zip")})
    assert r1.status_code == 200
    s1 = await _wait_install_status(r1.json()["request_id"])
    assert s1["status"] == "succeeded"

    v1 = _build_skill_zip(skill_id, "1.0.0")
    r2 = await _request("POST", "/v1/skill-packages/install", files={"file": ("v1.zip", v1, "application/zip")})
    assert r2.status_code == 200
    s2 = await _wait_install_status(r2.json()["request_id"])
    assert s2["status"] == "failed"
    assert "strictly higher version" in (s2.get("error") or "")


@pytest.mark.asyncio
async def test_reject_invalid_package_missing_required_files(isolated_skill_install_env):
    payload = _build_invalid_zip_missing_output_schema("demo-bad-upload", "1.0.0")
    res = await _request(
        "POST",
        "/v1/skill-packages/install",
        files={"file": ("bad.zip", payload, "application/zip")}
    )
    assert res.status_code == 200
    status = await _wait_install_status(res.json()["request_id"])
    assert status["status"] == "failed"
    assert "missing required files" in (status.get("error") or "")
