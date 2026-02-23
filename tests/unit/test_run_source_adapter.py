from pathlib import Path

from server.services.run_source_adapter import (
    get_request_and_run_dir,
    installed_run_source_adapter,
    temp_run_source_adapter,
)
from server.services.run_store import RunStore
from server.services.temp_skill_run_store import TempSkillRunStore


def test_source_capability_parity_matrix() -> None:
    installed = installed_run_source_adapter.capabilities
    temp = temp_run_source_adapter.capabilities

    assert installed.supports_pending_reply is True
    assert temp.supports_pending_reply is True
    assert installed.supports_event_history is True
    assert temp.supports_event_history is True
    assert installed.supports_log_range is True
    assert temp.supports_log_range is True
    assert installed_run_source_adapter.cache_namespace == "cache_entries"
    assert temp_run_source_adapter.cache_namespace == "temp_cache_entries"


def test_cache_lookup_namespace_isolated(tmp_path, monkeypatch) -> None:
    store = RunStore(db_path=tmp_path / "runs.db")
    store.record_cache_entry("shared-key", "run-installed")
    store.record_temp_cache_entry("shared-key", "run-temp")
    monkeypatch.setattr("server.services.run_source_adapter.run_store", store)

    assert installed_run_source_adapter.get_cached_run("shared-key") == "run-installed"
    assert temp_run_source_adapter.get_cached_run("shared-key") == "run-temp"


def test_temp_bind_cached_run_updates_both_stores(tmp_path, monkeypatch) -> None:
    store = RunStore(db_path=tmp_path / "runs.db")
    temp_store = TempSkillRunStore(db_path=tmp_path / "temp_runs.db")
    temp_store.create_request(
        request_id="temp-req-1",
        engine="gemini",
        parameter={},
        model=None,
        engine_options={},
        runtime_options={"execution_mode": "interactive"},
    )
    store.create_request(
        request_id="temp-req-1",
        skill_id="skill-temp",
        engine="gemini",
        input_data={},
        parameter={},
        engine_options={},
        runtime_options={"execution_mode": "interactive"},
    )

    monkeypatch.setattr("server.services.run_source_adapter.run_store", store)
    monkeypatch.setattr("server.services.run_source_adapter.temp_skill_run_store", temp_store)

    temp_run_source_adapter.bind_cached_run("temp-req-1", "run-cached-temp-1")

    temp_record = temp_store.get_request("temp-req-1")
    assert temp_record is not None
    assert temp_record["run_id"] == "run-cached-temp-1"

    regular_record = store.get_request("temp-req-1")
    assert regular_record is not None
    assert regular_record["run_id"] == "run-cached-temp-1"


def test_get_request_and_run_dir_reads_source_request(tmp_path, monkeypatch) -> None:
    store = RunStore(db_path=tmp_path / "runs.db")
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    store.create_request(
        request_id="req-1",
        skill_id="demo",
        engine="gemini",
        input_data={},
        parameter={},
        engine_options={},
        runtime_options={},
    )
    store.update_request_run_id("req-1", "run-1")

    monkeypatch.setattr("server.services.run_source_adapter.run_store", store)
    monkeypatch.setattr(
        "server.services.run_source_adapter.workspace_manager.get_run_dir",
        lambda run_id: run_dir if run_id == "run-1" else None,
    )

    record, resolved_dir = get_request_and_run_dir(installed_run_source_adapter, "req-1")
    assert record["request_id"] == "req-1"
    assert isinstance(resolved_dir, Path)
    assert resolved_dir == run_dir
