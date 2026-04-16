import sqlite3

import pytest

from server.services.orchestration.run_store_database import RunStoreDatabase
from server.services.orchestration.run_store_interaction_store import RunInteractionStore, RunInteractiveRuntimeStore


@pytest.mark.asyncio
async def test_run_interaction_store_pending_interaction_roundtrip(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    store = RunInteractionStore(database)

    payload = {
        "interaction_id": 1,
        "kind": "choose_one",
        "prompt": "Select mode",
        "options": [{"label": "A", "value": "a"}],
    }
    await store.set_pending_interaction("req-1", payload)
    pending = await store.get_pending_interaction("req-1")
    assert pending is not None
    assert pending["interaction_id"] == 1
    assert pending["kind"] == "choose_one"


@pytest.mark.asyncio
async def test_run_interaction_store_reply_idempotency_and_consume(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    store = RunInteractionStore(database)
    await store.set_pending_interaction(
        "req-1",
        {"interaction_id": 7, "kind": "confirm", "prompt": "Continue?"},
    )

    first = await store.submit_interaction_reply("req-1", 7, {"answer": "yes"}, "dup")
    second = await store.submit_interaction_reply("req-1", 7, {"answer": "yes"}, "dup")
    consumed = await store.consume_interaction_reply("req-1", 7)

    assert first == "accepted"
    assert second == "idempotent"
    assert consumed == {"answer": "yes"}


@pytest.mark.asyncio
async def test_run_interaction_store_history_and_auto_decision_stats(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    store = RunInteractionStore(database)

    await store.append_interaction_history(
        request_id="req-1",
        interaction_id=1,
        event_type="reply",
        source_attempt=1,
        payload={
            "response": {"answer": "a"},
            "resolution_mode": "auto_decide_timeout",
            "resolved_at": "2026-02-16T00:00:03",
        },
    )

    history = await store.list_interaction_history("req-1")
    stats = await store.get_auto_decision_stats("req-1")
    assert len(history) == 1
    assert stats["auto_decision_count"] == 1
    assert stats["last_auto_decision_at"] == "2026-02-16T00:00:03"


@pytest.mark.asyncio
async def test_run_interactive_runtime_store_roundtrip(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    store = RunInteractiveRuntimeStore(database)

    await store.set_effective_session_timeout("req-1", 1200)
    await store.set_interactive_profile("req-1", {"reason": "probe_ok", "session_timeout_sec": 1200})
    await store.set_engine_session_handle(
        "req-1",
        {
            "engine": "codex",
            "handle_type": "session_id",
            "handle_value": "thread-1",
            "created_at_turn": 1,
        },
    )

    profile = await store.get_interactive_profile("req-1")
    handle = await store.get_engine_session_handle("req-1")
    timeout = await store.get_effective_session_timeout("req-1")
    assert profile is not None
    assert profile["session_timeout_sec"] == 1200
    assert handle is not None
    assert handle["handle_value"] == "thread-1"
    assert timeout == 1200


@pytest.mark.asyncio
async def test_run_interaction_store_skips_legacy_invalid_rows(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    store = RunInteractionStore(database)
    await database.ensure_initialized()
    with sqlite3.connect(database.db_path) as conn:
        conn.execute(
            """
            INSERT INTO request_interaction_history (
                request_id, interaction_id, event_type, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "req-legacy",
                1,
                "ask_user",
                '{"prompt":"legacy-only"}',
                "2026-02-24T00:00:00",
            ),
        )
        conn.commit()

    rows = await store.list_interaction_history("req-legacy")
    assert rows == []
