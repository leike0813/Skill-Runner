from pathlib import Path
import sqlite3

import pytest

from server.services.orchestration.run_store import RunStore


@pytest.mark.asyncio
async def test_run_store_request_and_cache(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.create_request(
        request_id="req-1",
        skill_id="skill",
        engine="gemini",
        parameter={"a": 1},
        engine_options={"model": "x"},
        runtime_options={"no_cache": True}
    )
    request = await store.get_request("req-1")
    assert request is not None
    assert request["skill_id"] == "skill"
    assert request["parameter"]["a"] == 1

    await store.update_request_manifest("req-1", "/tmp/manifest.json", "hash")
    await store.update_request_cache_key("req-1", "cachekey", "skillfp")
    await store.create_run("run-1", "cachekey", "queued")
    await store.update_run_status("run-1", "succeeded")
    await store.record_cache_entry("cachekey", "run-1")
    assert await store.get_cached_run("cachekey") == "run-1"


@pytest.mark.asyncio
async def test_run_store_missing_request_returns_none(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    assert await store.get_request("missing") is None


@pytest.mark.asyncio
async def test_run_store_cache_miss_returns_none(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    assert await store.get_cached_run("missing") is None


@pytest.mark.asyncio
async def test_update_run_status_without_result_path(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.create_run("run-1", "cachekey", "queued")
    await store.update_run_status("run-1", "failed")


@pytest.mark.asyncio
async def test_update_run_status_with_result_path(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.create_run("run-1", "cachekey", "queued")
    await store.update_run_status("run-1", "succeeded", result_path="/tmp/result.json")

    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT result_path FROM runs WHERE run_id = ?", ("run-1",)).fetchone()
    assert row["result_path"] == "/tmp/result.json"


@pytest.mark.asyncio
async def test_set_pending_interaction_rejects_invalid_payload(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    with pytest.raises(ValueError, match="PROTOCOL_SCHEMA_VIOLATION"):
        await store.set_pending_interaction(
            "req-invalid",
            {
                "interaction_id": 1,
                "kind": "open_text",
            },
        )


@pytest.mark.asyncio
async def test_get_pending_interaction_ignores_invalid_legacy_payload(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.get_request("req-legacy")
    with sqlite3.connect(store.db_path) as conn:
        now = "2026-02-24T00:00:00"
        conn.execute(
            """
            INSERT INTO request_interactions (
                request_id, interaction_id, payload_json, state,
                idempotency_key, reply_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "req-legacy",
                5,
                '{"interaction_id":5,"prompt":"legacy-missing-kind"}',
                "pending",
                None,
                None,
                now,
                now,
            ),
        )
        conn.commit()
    assert await store.get_pending_interaction("req-legacy") is None
