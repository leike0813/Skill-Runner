from server.models import EngineUpgradeTaskStatus
from server.services.engine_upgrade_store import EngineUpgradeStore


def test_engine_upgrade_store_create_update_get(tmp_path):
    store = EngineUpgradeStore(tmp_path / "engine_upgrades.db")
    store.create_task("req-1", "single", "codex")
    assert store.has_running_task() is False

    store.update_task("req-1", status=EngineUpgradeTaskStatus.RUNNING)
    assert store.has_running_task() is True

    store.update_task(
        "req-1",
        status=EngineUpgradeTaskStatus.SUCCEEDED,
        results={"codex": {"status": "succeeded", "stdout": "ok", "stderr": "", "error": None}},
    )
    record = store.get_task("req-1")
    assert record is not None
    assert record["status"] == "succeeded"
    assert record["results"]["codex"]["status"] == "succeeded"
