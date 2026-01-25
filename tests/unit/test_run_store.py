from pathlib import Path
import sqlite3

from server.services.run_store import RunStore


def test_run_store_request_and_cache(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    store.create_request(
        request_id="req-1",
        skill_id="skill",
        engine="gemini",
        parameter={"a": 1},
        engine_options={"model": "x"},
        runtime_options={"verbose": True}
    )
    request = store.get_request("req-1")
    assert request is not None
    assert request["skill_id"] == "skill"
    assert request["parameter"]["a"] == 1

    store.update_request_manifest("req-1", "/tmp/manifest.json", "hash")
    store.update_request_cache_key("req-1", "cachekey", "skillfp")
    store.create_run("run-1", "cachekey", "queued")
    store.update_run_status("run-1", "succeeded")
    store.record_cache_entry("cachekey", "run-1")
    assert store.get_cached_run("cachekey") == "run-1"


def test_run_store_missing_request_returns_none(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    assert store.get_request("missing") is None


def test_run_store_cache_miss_returns_none(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    assert store.get_cached_run("missing") is None


def test_update_run_status_without_result_path(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    store.create_run("run-1", "cachekey", "queued")
    store.update_run_status("run-1", "failed")


def test_update_run_status_with_result_path(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    store.create_run("run-1", "cachekey", "queued")
    store.update_run_status("run-1", "succeeded", result_path="/tmp/result.json")

    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT result_path FROM runs WHERE run_id = ?", ("run-1",)).fetchone()
    assert row["result_path"] == "/tmp/result.json"
