from datetime import datetime

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from server.main import app


def test_install_skill_package_route(monkeypatch):
    client = TestClient(app)
    called = {"create": False, "run": False}

    def _create(request_id: str, package_bytes: bytes):
        called["create"] = True
        assert request_id
        assert package_bytes == b"zip-bytes"

    def _run(request_id: str):
        called["run"] = True

    monkeypatch.setattr("server.routers.skill_packages.skill_package_manager.create_install_request", _create)
    monkeypatch.setattr("server.routers.skill_packages.skill_package_manager.run_install", _run)

    response = client.post(
        "/v1/skill-packages/install",
        files={"file": ("skill.zip", b"zip-bytes", "application/zip")}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert "request_id" in body
    assert called["create"] is True
    assert called["run"] is True


def test_install_skill_package_rejects_empty_file():
    client = TestClient(app)
    response = client.post(
        "/v1/skill-packages/install",
        files={"file": ("skill.zip", b"", "application/zip")}
    )
    assert response.status_code == 400


def test_get_install_status(monkeypatch):
    client = TestClient(app)
    now = datetime.utcnow().isoformat()
    monkeypatch.setattr(
        "server.routers.skill_packages.skill_install_store.get_install",
        lambda request_id: {
            "request_id": request_id,
            "status": "succeeded",
            "created_at": now,
            "updated_at": now,
            "skill_id": "demo-upload",
            "version": "1.0.0",
            "action": "install",
            "error": None
        }
    )

    response = client.get("/v1/skill-packages/req-1")
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "req-1"
    assert body["status"] == "succeeded"
    assert body["skill_id"] == "demo-upload"


def test_get_install_status_not_found(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(
        "server.routers.skill_packages.skill_install_store.get_install",
        lambda _request_id: None
    )
    response = client.get("/v1/skill-packages/missing")
    assert response.status_code == 404
