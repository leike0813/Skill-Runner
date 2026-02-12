from datetime import datetime
from tempfile import SpooledTemporaryFile

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import BackgroundTasks, HTTPException, UploadFile

from server.routers import skill_packages as skill_packages_router


def _build_upload_file(payload: bytes) -> UploadFile:
    file_obj = SpooledTemporaryFile()
    file_obj.write(payload)
    file_obj.seek(0)
    return UploadFile(filename="skill.zip", file=file_obj)


@pytest.mark.asyncio
async def test_install_skill_package_route(monkeypatch):
    called = {"create": False, "run": False}

    def _create(request_id: str, package_bytes: bytes):
        called["create"] = True
        assert request_id
        assert package_bytes == b"zip-bytes"

    def _run(request_id: str):
        called["run"] = True
        assert request_id

    monkeypatch.setattr(
        "server.routers.skill_packages.skill_package_manager.create_install_request",
        _create
    )
    monkeypatch.setattr(
        "server.routers.skill_packages.skill_package_manager.run_install",
        _run
    )

    response = await skill_packages_router.install_skill_package(
        background_tasks=BackgroundTasks(),
        file=_build_upload_file(b"zip-bytes")
    )

    assert response.status == "queued"
    assert response.request_id
    assert called["create"] is True
    assert called["run"] is False


@pytest.mark.asyncio
async def test_install_skill_package_rejects_empty_file():
    with pytest.raises(HTTPException) as exc:
        await skill_packages_router.install_skill_package(
            background_tasks=BackgroundTasks(),
            file=_build_upload_file(b"")
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_get_install_status(monkeypatch):
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

    response = await skill_packages_router.get_install_status("req-1")
    assert response.request_id == "req-1"
    assert response.status == "succeeded"
    assert response.skill_id == "demo-upload"


@pytest.mark.asyncio
async def test_get_install_status_not_found(monkeypatch):
    monkeypatch.setattr(
        "server.routers.skill_packages.skill_install_store.get_install",
        lambda _request_id: None
    )
    with pytest.raises(HTTPException) as exc:
        await skill_packages_router.get_install_status("missing")
    assert exc.value.status_code == 404
