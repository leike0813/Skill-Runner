from pathlib import Path
import sqlite3

import pytest

from server.runtime.workspace_layout import require_layout_from_record
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
async def test_list_requests_with_runs_includes_workspace_layout(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    workspace_dir = tmp_path / "workspaces" / "run-1"
    await store.create_request(
        request_id="req-1",
        skill_id="skill",
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options={},
        input_data={},
    )
    await store.create_run(
        "run-1",
        None,
        "waiting_user",
        result_path=str(workspace_dir / "result" / "skill.1" / "result.json"),
        workspace_id="run-1",
        workspace_dir=str(workspace_dir),
        workspace_namespace="skill.1",
        input_manifest_path=str(workspace_dir / ".audit" / "skill.1" / "input_manifest.json"),
    )
    await store.update_request_run_id("req-1", "run-1")

    rows = await store.list_requests_with_runs_page(page=1, page_size=20)

    assert len(rows) == 1
    layout = require_layout_from_record(rows[0])
    assert layout.workspace_dir == workspace_dir
    assert layout.namespace == "skill.1"
    assert rows[0]["result_path"] == str(workspace_dir / "result" / "skill.1" / "result.json")
    assert rows[0]["run_input_manifest_path"] == str(
        workspace_dir / ".audit" / "skill.1" / "input_manifest.json"
    )


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
    await store._ensure_initialized()
    async with store._interaction_database.connect() as conn:
        now = "2026-02-24T00:00:00"
        await conn.execute(
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
        await conn.commit()
    assert await store.get_pending_interaction("req-legacy") is None
