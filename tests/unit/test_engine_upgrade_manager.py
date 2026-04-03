import pytest

from server.services.engine_management.engine_upgrade_manager import (
    EngineUpgradeBusyError,
    EngineUpgradeManager,
    EngineUpgradeValidationError,
)
from server.models import EngineUpgradeTaskStatus
from server.services.engine_management.engine_upgrade_store import EngineUpgradeStore


def _build_manager_with_store(tmp_path):
    store = EngineUpgradeStore(tmp_path / "runs.db")
    manager = EngineUpgradeManager()
    manager._store = store  # type: ignore[attr-defined]
    return manager, store


@pytest.mark.asyncio
async def test_create_task_rejects_invalid_payload(tmp_path):
    manager, _store = _build_manager_with_store(tmp_path)

    with pytest.raises(EngineUpgradeValidationError):
        await manager.create_task("bad", None)

    with pytest.raises(EngineUpgradeValidationError):
        await manager.create_task("single", None)

    with pytest.raises(EngineUpgradeValidationError):
        await manager.create_task("single", "unknown")

    assert manager._resolve_engines("single", "opencode") == ["opencode"]


@pytest.mark.asyncio
async def test_create_task_rejects_when_busy(tmp_path):
    manager, store = _build_manager_with_store(tmp_path)
    await store.create_task("req-running", "all", None)
    await store.update_task("req-running", status=EngineUpgradeTaskStatus.RUNNING)

    with pytest.raises(EngineUpgradeBusyError):
        await manager.create_task("all", None)


@pytest.mark.asyncio
async def test_run_task_single_success(tmp_path, monkeypatch):
    manager, store = _build_manager_with_store(tmp_path)
    await store.create_task("req-1", "single", "gemini")
    manager._running_request_id = "req-1"  # type: ignore[attr-defined]
    refreshed_engines: list[str] = []

    async def _fake_run(_engine: str, *, mode: str):
        assert mode == "single"
        return {"status": "succeeded", "action": "upgrade", "stdout": "ok", "stderr": "", "error": None}
    async def _noop_refresh_status(_engine: str):
        return None

    monkeypatch.setattr(manager, "_run_single_engine_task", _fake_run)
    monkeypatch.setattr(manager, "_refresh_engine_status_cache", _noop_refresh_status)
    monkeypatch.setattr(
        "server.services.engine_management.engine_upgrade_manager.model_registry.refresh",
        lambda engine=None: refreshed_engines.append(str(engine)),
    )
    await manager._run_task("req-1")

    record = await store.get_task("req-1")
    assert record is not None
    assert record["status"] == "succeeded"
    assert record["results"]["gemini"]["status"] == "succeeded"
    assert record["results"]["gemini"]["action"] == "upgrade"
    assert "gemini" in refreshed_engines


@pytest.mark.asyncio
async def test_run_task_all_with_failure(tmp_path, monkeypatch):
    manager, store = _build_manager_with_store(tmp_path)
    await store.create_task("req-2", "all", None)
    manager._running_request_id = "req-2"  # type: ignore[attr-defined]

    async def _fake_run(engine: str, *, mode: str):
        assert mode == "all"
        if engine == "gemini":
            return {"status": "failed", "action": "upgrade", "stdout": "", "stderr": "boom", "error": "failed"}
        return {"status": "succeeded", "action": "upgrade", "stdout": "ok", "stderr": "", "error": None}
    async def _noop_refresh_status(_engine: str):
        return None

    monkeypatch.setattr(manager, "_run_single_engine_task", _fake_run)
    monkeypatch.setattr(manager, "_refresh_engine_status_cache", _noop_refresh_status)
    await manager._run_task("req-2")

    record = await store.get_task("req-2")
    assert record is not None
    assert record["status"] == "failed"
    assert record["results"]["gemini"]["status"] == "failed"
    assert record["results"]["gemini"]["action"] == "upgrade"


def test_single_engine_action_uses_install_when_managed_missing(tmp_path, monkeypatch):
    manager, _store = _build_manager_with_store(tmp_path)
    monkeypatch.setattr(manager._cli_manager, "resolve_managed_engine_command", lambda _engine: None)
    assert manager._resolve_single_engine_action("codex") == "install"


def test_single_engine_action_uses_upgrade_when_managed_present(tmp_path, monkeypatch):
    manager, _store = _build_manager_with_store(tmp_path)
    monkeypatch.setattr(manager._cli_manager, "resolve_managed_engine_command", lambda _engine: object())
    assert manager._resolve_single_engine_action("codex") == "upgrade"
