from pathlib import Path

import pytest

from server.runtime.observability.run_source_adapter import (
    get_request_and_run_dir,
    installed_run_source_adapter,
)
from server.services.orchestration.run_store import RunStore
from tests.common.workspace_layout_helpers import seed_request_bound_store


def test_installed_source_capability_matrix() -> None:
    installed = installed_run_source_adapter.capabilities

    assert installed.supports_pending_reply is True
    assert installed.supports_event_history is True
    assert installed.supports_log_range is True
    assert installed.supports_inline_input_create is True
    assert installed_run_source_adapter.cache_namespace == "cache_entries"


@pytest.mark.asyncio
async def test_cache_lookup_reads_installed_namespace(tmp_path, monkeypatch) -> None:
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.record_cache_entry("shared-key", "run-installed")
    await store.record_temp_cache_entry("shared-key", "run-temp")
    monkeypatch.setattr("server.runtime.observability.run_source_adapter.run_store", store)

    assert await installed_run_source_adapter.get_cached_run("shared-key") == "run-installed"


@pytest.mark.asyncio
async def test_get_request_and_run_dir_reads_source_request(tmp_path, monkeypatch) -> None:
    store = RunStore(db_path=tmp_path / "runs.db")
    run_dir = tmp_path / "workspaces" / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    await seed_request_bound_store(
        store,
        request_id="req-1",
        run_id="run-1",
        workspace=run_dir,
        engine="codex",
        skill_id="demo",
    )

    monkeypatch.setattr("server.runtime.observability.run_source_adapter.run_store", store)

    record, resolved_dir = await get_request_and_run_dir(installed_run_source_adapter, "req-1")
    assert record["request_id"] == "req-1"
    assert isinstance(resolved_dir, Path)
    assert resolved_dir == run_dir
