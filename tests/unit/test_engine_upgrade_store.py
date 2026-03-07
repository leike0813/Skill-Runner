import pytest

from server.models import EngineUpgradeTaskStatus
from server.services.engine_management.engine_upgrade_store import EngineUpgradeStore


@pytest.mark.asyncio
async def test_engine_upgrade_store_create_update_get(tmp_path):
    store = EngineUpgradeStore(tmp_path / "runs.db")
    await store.create_task("req-1", "single", "codex")
    assert await store.has_running_task() is False

    await store.update_task("req-1", status=EngineUpgradeTaskStatus.RUNNING)
    assert await store.has_running_task() is True

    await store.update_task(
        "req-1",
        status=EngineUpgradeTaskStatus.SUCCEEDED,
        results={"codex": {"status": "succeeded", "stdout": "ok", "stderr": "", "error": None}},
    )
    record = await store.get_task("req-1")
    assert record is not None
    assert record["status"] == "succeeded"
    assert record["results"]["codex"]["status"] == "succeeded"
