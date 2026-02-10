import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from server.main import app


@pytest.mark.parametrize(
    "path",
    [
        "/skills",
        "/runs",
        "/engines",
        "/runs/does-not-exist",
        "/engines/codex/models"
    ]
)
def test_legacy_routes_return_404(path):
    client = TestClient(app)
    response = client.get(path)
    assert response.status_code == 404


def test_v1_skills_route_available(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(
        "server.routers.skills.skill_registry.list_skills",
        lambda: []
    )
    response = client.get("/v1/skills")
    assert response.status_code == 200
    assert response.json() == []


def test_v1_engines_route_available(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(
        "server.routers.engines.model_registry.list_engines",
        lambda: [{"engine": "codex", "cli_version_detected": "0.89.0"}]
    )
    response = client.get("/v1/engines")
    assert response.status_code == 200
    body = response.json()
    assert body["engines"][0]["engine"] == "codex"


def test_v1_engine_models_route_available(monkeypatch):
    client = TestClient(app)
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
                            "supported_effort": ["low", "high"]
                        }
                    )()
                ]
            }
        )()
    )
    response = client.get("/v1/engines/codex/models")
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "codex"
    assert body["models"][0]["id"] == "gpt-5.2-codex"


def test_v1_engine_models_not_found(monkeypatch):
    client = TestClient(app)

    def _raise(_engine: str):
        raise ValueError("Unknown engine")

    monkeypatch.setattr("server.routers.engines.model_registry.get_models", _raise)
    response = client.get("/v1/engines/unknown/models")
    assert response.status_code == 404


def test_v1_engine_models_error(monkeypatch):
    client = TestClient(app)

    def _raise(_engine: str):
        raise RuntimeError("boom")

    monkeypatch.setattr("server.routers.engines.model_registry.get_models", _raise)
    response = client.get("/v1/engines/codex/models")
    assert response.status_code == 500

def test_v1_runs_route_available():
    client = TestClient(app)
    response = client.get("/v1/jobs/does-not-exist")
    assert response.status_code == 404


def test_v1_jobs_cleanup_route(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(
        "server.routers.jobs.run_cleanup_manager.clear_all",
        lambda: {"runs": 1, "requests": 2, "cache_entries": 3}
    )
    response = client.post("/v1/jobs/cleanup")
    assert response.status_code == 200
    body = response.json()
    assert body["runs_deleted"] == 1
    assert body["requests_deleted"] == 2
    assert body["cache_entries_deleted"] == 3


def test_v1_temp_skill_runs_route_available():
    client = TestClient(app)
    response = client.get("/v1/temp-skill-runs/does-not-exist")
    assert response.status_code == 404
