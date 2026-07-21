import sqlite3
import asyncio

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
async def test_run_interaction_store_persists_file_fingerprint_public_response_and_receipt(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    store = RunInteractionStore(database)
    await store.set_pending_interaction(
        "req-1",
        {"interaction_id": 17, "kind": "upload_files", "prompt": "Upload"},
    )
    private = {
        "kind": "interaction_files",
        "files": [{"slot": "paper", "name": "paper.pdf", "path": "uploads/x", "size_bytes": 3}],
    }
    public = {
        "kind": "interaction_files",
        "files": [{"slot": "paper", "name": "paper.pdf", "size_bytes": 3}],
    }
    receipt = {"request_id": "req-1", "status": "queued", "accepted": True, "mode": "interaction"}

    first = await store.submit_interaction_reply(
        "req-1",
        17,
        private,
        "key-1",
        public_response=public,
        idempotency_fingerprint="a" * 64,
        receipt=receipt,
    )
    replay = await store.submit_interaction_reply(
        "req-1",
        17,
        {**private, "files": [{**private["files"][0], "path": "uploads/random-replay"}]},
        "key-1",
        public_response=public,
        idempotency_fingerprint="a" * 64,
        receipt=receipt,
    )
    conflict = await store.submit_interaction_reply(
        "req-1",
        17,
        private,
        "key-1",
        idempotency_fingerprint="b" * 64,
    )
    record = await store.get_interaction_reply_record("req-1", 17, "key-1")

    assert first == "accepted"
    assert replay == "idempotent"
    assert conflict == "idempotency_conflict"
    assert record is not None
    assert record["response"] == private
    assert record["public_response"] == public
    assert record["receipt"] == receipt


@pytest.mark.asyncio
async def test_run_interaction_store_concurrent_file_replies_have_one_winner(tmp_path):
    database = RunStoreDatabase(tmp_path / "runs.db")
    store = RunInteractionStore(database)
    await store.set_pending_interaction(
        "req-1",
        {"interaction_id": 19, "kind": "upload_files", "prompt": "Upload"},
    )

    async def submit(key: str, fingerprint: str) -> str:
        return await store.submit_interaction_reply(
            "req-1",
            19,
            {"kind": "interaction_files", "key": key},
            key,
            idempotency_fingerprint=fingerprint,
        )

    results = await asyncio.gather(submit("key-a", "a" * 64), submit("key-b", "b" * 64))
    assert sorted(results) == ["accepted", "stale"]


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
