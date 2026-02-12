import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from server.main import app
from server.services.engine_upgrade_manager import EngineUpgradeBusyError, EngineUpgradeValidationError


async def _request(method: str, path: str, **kwargs):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, **kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/skills",
        "/runs",
        "/engines",
        "/runs/does-not-exist",
        "/engines/codex/models",
    ],
)
async def test_legacy_routes_return_404(path):
    response = await _request("GET", path)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_v1_skills_route_available(monkeypatch):
    monkeypatch.setattr(
        "server.routers.skills.skill_registry.list_skills",
        lambda: [],
    )
    response = await _request("GET", "/v1/skills")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_v1_engines_route_available(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.model_registry.list_engines",
        lambda: [{"engine": "codex", "cli_version_detected": "0.89.0"}],
    )
    response = await _request("GET", "/v1/engines")
    assert response.status_code == 200
    body = response.json()
    assert body["engines"][0]["engine"] == "codex"


@pytest.mark.asyncio
async def test_v1_engine_models_route_available(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.model_registry.get_models",
        lambda engine: type(
            "Catalog",
            (),
            {
                "engine": engine,
                "cli_version_detected": "0.89.0",
                "snapshot_version_used": "0.89.0",
                "fallback_reason": None,
                "models": [
                    type(
                        "Entry",
                        (),
                        {
                            "id": "gpt-5.2-codex",
                            "display_name": "GPT-5.2 Codex",
                            "deprecated": False,
                            "notes": "snapshot",
                            "supported_effort": ["low", "high"],
                        },
                    )()
                ],
            },
        )(),
    )
    response = await _request("GET", "/v1/engines/codex/models")
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "codex"
    assert body["models"][0]["id"] == "gpt-5.2-codex"


@pytest.mark.asyncio
async def test_v1_engine_models_not_found(monkeypatch):
    def _raise(_engine: str):
        raise ValueError("Unknown engine")

    monkeypatch.setattr("server.routers.engines.model_registry.get_models", _raise)
    response = await _request("GET", "/v1/engines/unknown/models")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_v1_engine_models_error(monkeypatch):
    def _raise(_engine: str):
        raise RuntimeError("boom")

    monkeypatch.setattr("server.routers.engines.model_registry.get_models", _raise)
    response = await _request("GET", "/v1/engines/codex/models")
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_v1_runs_route_available():
    response = await _request("GET", "/v1/jobs/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_v1_jobs_cleanup_route(monkeypatch):
    monkeypatch.setattr(
        "server.routers.jobs.run_cleanup_manager.clear_all",
        lambda: {"runs": 1, "requests": 2, "cache_entries": 3},
    )
    response = await _request("POST", "/v1/jobs/cleanup")
    assert response.status_code == 200
    body = response.json()
    assert body["runs_deleted"] == 1
    assert body["requests_deleted"] == 2
    assert body["cache_entries_deleted"] == 3


@pytest.mark.asyncio
async def test_v1_temp_skill_runs_route_available():
    response = await _request("GET", "/v1/temp-skill-runs/does-not-exist")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_v1_engine_upgrade_create_route(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.engine_upgrade_manager.create_task",
        lambda mode, engine: "upgrade-1",
    )
    response = await _request("POST", "/v1/engines/upgrades", json={"mode": "all"})
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "upgrade-1"
    assert body["status"] == "queued"


@pytest.mark.asyncio
async def test_v1_engine_upgrade_create_conflict(monkeypatch):
    def _raise(_mode, _engine):
        raise EngineUpgradeBusyError("busy")

    monkeypatch.setattr("server.routers.engines.engine_upgrade_manager.create_task", _raise)
    response = await _request("POST", "/v1/engines/upgrades", json={"mode": "all"})
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_v1_engine_upgrade_create_validation_error(monkeypatch):
    def _raise(_mode, _engine):
        raise EngineUpgradeValidationError("bad payload")

    monkeypatch.setattr("server.routers.engines.engine_upgrade_manager.create_task", _raise)
    response = await _request("POST", "/v1/engines/upgrades", json={"mode": "bad"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_v1_engine_upgrade_status_route(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.engine_upgrade_manager.get_task",
        lambda _request_id: {
            "request_id": "upgrade-1",
            "mode": "all",
            "requested_engine": None,
            "status": "running",
            "results": {
                "codex": {"status": "succeeded", "stdout": "ok", "stderr": "", "error": None}
            },
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:01",
        },
    )
    response = await _request("GET", "/v1/engines/upgrades/upgrade-1")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["results"]["codex"]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_v1_engine_manifest_route(monkeypatch):
    monkeypatch.setattr(
        "server.routers.engines.model_registry.get_manifest_view",
        lambda _engine: {
            "engine": "codex",
            "cli_version_detected": "0.89.0",
            "manifest": {"engine": "codex", "snapshots": []},
            "resolved_snapshot_version": "0.89.0",
            "resolved_snapshot_file": "models_0.89.0.json",
            "fallback_reason": None,
            "models": [{"id": "gpt-5.2-codex", "deprecated": False}],
        },
    )
    response = await _request("GET", "/v1/engines/codex/models/manifest")
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "codex"
    assert body["resolved_snapshot_file"] == "models_0.89.0.json"


@pytest.mark.asyncio
async def test_v1_engine_snapshot_route_conflict(monkeypatch):
    def _raise(_engine, _models):
        raise ValueError("Snapshot already exists for version 0.89.0")

    monkeypatch.setattr("server.routers.engines.model_registry.add_snapshot_for_detected_version", _raise)
    response = await _request(
        "POST",
        "/v1/engines/codex/models/snapshots",
        json={"models": [{"id": "gpt-5.2-codex"}]},
    )
    assert response.status_code == 409
