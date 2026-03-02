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
async def test_run_store_regular_and_temp_cache_are_isolated(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.record_cache_entry("shared-key", "run-regular")
    await store.record_temp_cache_entry("shared-key", "run-temp")
    assert await store.get_cached_run("shared-key") == "run-regular"
    assert await store.get_temp_cached_run("shared-key") == "run-temp"


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
async def test_list_active_run_ids(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.create_run("run-q", "k1", "queued")
    await store.create_run("run-r", "k2", "running")
    await store.create_run("run-w", "k4", "waiting_user")
    await store.create_run("run-s", "k3", "succeeded")
    active = set(await store.list_active_run_ids())
    assert active == {"run-q", "run-r", "run-w"}


@pytest.mark.asyncio
async def test_cancel_requested_roundtrip(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.create_run("run-1", None, "queued")
    assert await store.is_cancel_requested("run-1") is False
    changed = await store.set_cancel_requested("run-1", True)
    assert changed is True
    assert await store.is_cancel_requested("run-1") is True
    changed_again = await store.set_cancel_requested("run-1", True)
    assert changed_again is False


@pytest.mark.asyncio
async def test_pending_interaction_roundtrip(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
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
async def test_submit_interaction_reply_idempotent(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.set_pending_interaction(
        "req-1",
        {
            "interaction_id": 7,
            "kind": "confirm",
            "prompt": "Continue?",
        },
    )
    first = await store.submit_interaction_reply(
        request_id="req-1",
        interaction_id=7,
        response={"answer": "yes"},
        idempotency_key="dup",
    )
    second = await store.submit_interaction_reply(
        request_id="req-1",
        interaction_id=7,
        response={"answer": "yes"},
        idempotency_key="dup",
    )
    conflict = await store.submit_interaction_reply(
        request_id="req-1",
        interaction_id=7,
        response={"answer": "no"},
        idempotency_key="dup",
    )
    assert first == "accepted"
    assert second == "idempotent"
    assert conflict == "idempotency_conflict"


@pytest.mark.asyncio
async def test_interactive_runtime_roundtrip(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.set_effective_session_timeout("req-1", 1200)
    await store.set_interactive_profile(
        "req-1",
        {"reason": "probe_ok", "session_timeout_sec": 1200},
    )
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
    effective_timeout = await store.get_effective_session_timeout("req-1")
    assert profile is not None
    assert profile["session_timeout_sec"] == 1200
    assert handle is not None
    assert handle["handle_value"] == "thread-1"
    assert effective_timeout == 1200


@pytest.mark.asyncio
async def test_get_request_by_run_id(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.create_request(
        request_id="req-1",
        skill_id="skill",
        engine="gemini",
        parameter={},
        engine_options={},
        runtime_options={"execution_mode": "interactive"},
        input_data={"foo": "bar"},
    )
    await store.create_run("run-1", None, "queued")
    await store.update_request_run_id("req-1", "run-1")
    request = await store.get_request_by_run_id("run-1")
    assert request is not None
    assert request["request_id"] == "req-1"
    assert request["input"]["foo"] == "bar"


@pytest.mark.asyncio
async def test_interaction_history_and_consume_reply(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.set_pending_interaction(
        "req-1",
        {"interaction_id": 2, "kind": "choose_one", "prompt": "Pick one"},
    )
    await store.append_interaction_history(
        request_id="req-1",
        interaction_id=2,
        event_type="ask_user",
        payload={
            "interaction_id": 2,
            "kind": "choose_one",
            "prompt": "Pick one",
            "options": [],
        },
    )
    accepted = await store.submit_interaction_reply(
        request_id="req-1",
        interaction_id=2,
        response={"answer": "a"},
        idempotency_key="k2",
    )
    consumed = await store.consume_interaction_reply("req-1", 2)
    history = await store.list_interaction_history("req-1")
    assert accepted == "accepted"
    assert consumed == {"answer": "a"}
    assert len(history) == 1
    assert history[0]["event_type"] == "ask_user"


@pytest.mark.asyncio
async def test_auto_decision_stats(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.append_interaction_history(
        request_id="req-1",
        interaction_id=1,
        event_type="reply",
        payload={
            "response": {"answer": "a"},
            "resolution_mode": "auto_decide_timeout",
            "resolved_at": "2026-02-16T00:00:01",
        },
    )
    await store.append_interaction_history(
        request_id="req-1",
        interaction_id=2,
        event_type="reply",
        payload={
            "response": {"answer": "b"},
            "resolution_mode": "user_reply",
            "resolved_at": "2026-02-16T00:00:02",
        },
    )
    await store.append_interaction_history(
        request_id="req-1",
        interaction_id=3,
        event_type="reply",
        payload={
            "response": {"answer": "c"},
            "resolution_mode": "auto_decide_timeout",
            "resolved_at": "2026-02-16T00:00:03",
        },
    )
    stats = await store.get_auto_decision_stats("req-1")
    assert stats["auto_decision_count"] == 2
    assert stats["last_auto_decision_at"] == "2026-02-16T00:00:03"


@pytest.mark.asyncio
async def test_recovery_metadata_and_incomplete_scan_roundtrip(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.create_request(
        request_id="req-1",
        skill_id="skill",
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options={"execution_mode": "interactive"},
        input_data={},
    )
    await store.create_run("run-1", None, "waiting_user")
    await store.update_request_run_id("req-1", "run-1")
    await store.set_interactive_profile(
        "req-1",
        {"reason": "probe_ok", "session_timeout_sec": 1200},
    )
    await store.set_engine_session_handle(
        "req-1",
        {
            "engine": "codex",
            "handle_type": "session_id",
            "handle_value": "thread-1",
            "created_at_turn": 1,
        },
    )
    await store.set_recovery_info(
        "run-1",
        recovery_state="recovered_waiting",
        recovery_reason="resumable_waiting_preserved",
        recovered_at="2026-02-16T00:00:00",
    )

    info = await store.get_recovery_info("run-1")
    assert info["recovery_state"] == "recovered_waiting"
    assert info["recovered_at"] == "2026-02-16T00:00:00"
    assert info["recovery_reason"] == "resumable_waiting_preserved"

    rows = await store.list_incomplete_runs()
    assert len(rows) == 1
    assert rows[0]["run_status"] == "waiting_user"
    assert rows[0]["interactive_session_config"]["session_timeout_sec"] == 1200
    assert rows[0]["session_handle"]["handle_value"] == "thread-1"

    await store.clear_engine_session_handle("req-1")
    assert await store.get_engine_session_handle("req-1") is None


@pytest.mark.asyncio
async def test_migrate_legacy_interactive_runtime_table(tmp_path):
    db_path = tmp_path / "runs.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE request_interactive_runtime (
                request_id TEXT PRIMARY KEY,
                profile_json TEXT,
                effective_session_timeout_sec INTEGER,
                session_handle_json TEXT,
                wait_deadline_at TEXT,
                process_binding_json TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO request_interactive_runtime (
                request_id, profile_json, effective_session_timeout_sec,
                session_handle_json, wait_deadline_at, process_binding_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "req-legacy",
                '{"kind":"sticky_process","session_timeout_sec":900}',
                None,
                '{"engine":"codex","handle_type":"session_id","handle_value":"thread-1","created_at_turn":1}',
                "2099-01-01T00:00:00",
                '{"run_id":"run-1","alive":true}',
                "2026-02-23T00:00:00",
            ),
        )
        conn.commit()

    store = RunStore(db_path=db_path)
    await store.get_request("req-legacy")
    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(request_interactive_runtime)").fetchall()
        }
        row = conn.execute(
            "SELECT request_id, effective_session_timeout_sec, session_handle_json FROM request_interactive_runtime WHERE request_id = ?",
            ("req-legacy",),
        ).fetchone()

    assert cols == {
        "request_id",
        "effective_session_timeout_sec",
        "session_handle_json",
        "updated_at",
    }
    assert row["request_id"] == "req-legacy"
    assert row["effective_session_timeout_sec"] == 900
    assert '"handle_value":"thread-1"' in row["session_handle_json"]


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
async def test_list_interaction_history_skips_legacy_invalid_rows(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    await store.get_request("req-legacy")
    with sqlite3.connect(store.db_path) as conn:
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
        conn.execute(
            """
            INSERT INTO request_interaction_history (
                request_id, interaction_id, event_type, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "req-legacy",
                2,
                "reply",
                '{"response":{"ok":true},"resolution_mode":"user_reply","resolved_at":"2026-02-24T00:00:01"}',
                "2026-02-24T00:00:01",
            ),
        )
        conn.commit()

    rows = await store.list_interaction_history("req-legacy")
    assert len(rows) == 1
    assert rows[0]["interaction_id"] == 2


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
