import pytest

from server.services.orchestration.run_store_cache_store import RunCacheStore
from server.services.orchestration.run_store_database import RunStoreDatabase


@pytest.mark.asyncio
async def test_run_cache_store_regular_and_temp_cache_are_isolated(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    cache_store = RunCacheStore(database)

    await cache_store.record_cache_entry("shared-key", "run-regular")
    await cache_store.record_temp_cache_entry("shared-key", "run-temp")

    assert await cache_store.get_cached_run("shared-key") == "run-regular"
    assert await cache_store.get_temp_cached_run("shared-key") == "run-temp"


@pytest.mark.asyncio
async def test_run_cache_store_cache_miss_returns_none(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    cache_store = RunCacheStore(database)

    assert await cache_store.get_cached_run("missing") is None


@pytest.mark.asyncio
async def test_run_cache_store_get_cached_run_for_source_uses_temp_upload(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    cache_store = RunCacheStore(database)

    await cache_store.record_cache_entry("shared-key", "run-regular")
    await cache_store.record_temp_cache_entry("shared-key", "run-temp")

    assert await cache_store.get_cached_run_for_source("shared-key", "temp_upload") == "run-temp"
    assert await cache_store.get_cached_run_for_source("shared-key", "installed") == "run-regular"
