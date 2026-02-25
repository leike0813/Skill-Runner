import pytest

from server.services.engine_upgrade_manager import (
    EngineUpgradeBusyError,
    EngineUpgradeManager,
    EngineUpgradeValidationError,
)
from server.models import EngineUpgradeTaskStatus
from server.services.engine_upgrade_store import EngineUpgradeStore


def _build_manager_with_store(tmp_path):
    store = EngineUpgradeStore(tmp_path / "engine_upgrades.db")
    manager = EngineUpgradeManager()
    manager._store = store  # type: ignore[attr-defined]
    return manager, store


@pytest.mark.asyncio
async def test_create_task_rejects_invalid_payload(tmp_path):
    manager, _store = _build_manager_with_store(tmp_path)

    with pytest.raises(EngineUpgradeValidationError):
        manager.create_task("bad", None)

    with pytest.raises(EngineUpgradeValidationError):
        manager.create_task("single", None)

    with pytest.raises(EngineUpgradeValidationError):
        manager.create_task("single", "unknown")

    assert manager._resolve_engines("single", "opencode") == ["opencode"]


@pytest.mark.asyncio
async def test_create_task_rejects_when_busy(tmp_path):
    manager, store = _build_manager_with_store(tmp_path)
    store.create_task("req-running", "all", None)
    store.update_task("req-running", status=EngineUpgradeTaskStatus.RUNNING)

    with pytest.raises(EngineUpgradeBusyError):
        manager.create_task("all", None)


@pytest.mark.asyncio
async def test_run_task_single_success(tmp_path, monkeypatch):
    manager, store = _build_manager_with_store(tmp_path)
    store.create_task("req-1", "single", "gemini")
    manager._running_request_id = "req-1"  # type: ignore[attr-defined]

    async def _fake_run(_engine: str):
        return {"status": "succeeded", "stdout": "ok", "stderr": "", "error": None}

    monkeypatch.setattr(manager, "_run_single_engine_upgrade", _fake_run)
    await manager._run_task("req-1")

    record = store.get_task("req-1")
    assert record is not None
    assert record["status"] == "succeeded"
    assert record["results"]["gemini"]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_run_task_all_with_failure(tmp_path, monkeypatch):
    manager, store = _build_manager_with_store(tmp_path)
    store.create_task("req-2", "all", None)
    manager._running_request_id = "req-2"  # type: ignore[attr-defined]

    async def _fake_run(engine: str):
        if engine == "gemini":
            return {"status": "failed", "stdout": "", "stderr": "boom", "error": "failed"}
        return {"status": "succeeded", "stdout": "ok", "stderr": "", "error": None}

    monkeypatch.setattr(manager, "_run_single_engine_upgrade", _fake_run)
    await manager._run_task("req-2")

    record = store.get_task("req-2")
    assert record is not None
    assert record["status"] == "failed"
    assert record["results"]["gemini"]["status"] == "failed"
