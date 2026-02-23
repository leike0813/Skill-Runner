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


def test_run_store_regular_and_temp_cache_are_isolated(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    store.record_cache_entry("shared-key", "run-regular")
    store.record_temp_cache_entry("shared-key", "run-temp")
    assert store.get_cached_run("shared-key") == "run-regular"
    assert store.get_temp_cached_run("shared-key") == "run-temp"


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


def test_list_active_run_ids(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    store.create_run("run-q", "k1", "queued")
    store.create_run("run-r", "k2", "running")
    store.create_run("run-w", "k4", "waiting_user")
    store.create_run("run-s", "k3", "succeeded")
    active = set(store.list_active_run_ids())
    assert active == {"run-q", "run-r", "run-w"}


def test_cancel_requested_roundtrip(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    store.create_run("run-1", None, "queued")
    assert store.is_cancel_requested("run-1") is False
    changed = store.set_cancel_requested("run-1", True)
    assert changed is True
    assert store.is_cancel_requested("run-1") is True
    changed_again = store.set_cancel_requested("run-1", True)
    assert changed_again is False


def test_pending_interaction_roundtrip(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    payload = {
        "interaction_id": 1,
        "kind": "choose_one",
        "prompt": "Select mode",
        "options": [{"label": "A", "value": "a"}],
    }
    store.set_pending_interaction("req-1", payload)
    pending = store.get_pending_interaction("req-1")
    assert pending is not None
    assert pending["interaction_id"] == 1
    assert pending["kind"] == "choose_one"


def test_submit_interaction_reply_idempotent(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    store.set_pending_interaction(
        "req-1",
        {
            "interaction_id": 7,
            "kind": "confirm",
            "prompt": "Continue?",
        },
    )
    first = store.submit_interaction_reply(
        request_id="req-1",
        interaction_id=7,
        response={"answer": "yes"},
        idempotency_key="dup",
    )
    second = store.submit_interaction_reply(
        request_id="req-1",
        interaction_id=7,
        response={"answer": "yes"},
        idempotency_key="dup",
    )
    conflict = store.submit_interaction_reply(
        request_id="req-1",
        interaction_id=7,
        response={"answer": "no"},
        idempotency_key="dup",
    )
    assert first == "accepted"
    assert second == "idempotent"
    assert conflict == "idempotency_conflict"


def test_interactive_runtime_roundtrip(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    store.set_effective_session_timeout("req-1", 1200)
    store.set_interactive_profile(
        "req-1",
        {"kind": "resumable", "reason": "probe_ok", "session_timeout_sec": 1200},
    )
    store.set_engine_session_handle(
        "req-1",
        {
            "engine": "codex",
            "handle_type": "session_id",
            "handle_value": "thread-1",
            "created_at_turn": 1,
        },
    )
    store.set_sticky_wait_runtime(
        "req-1",
        "2026-02-16T00:00:00",
        {"run_id": "run-1", "alive": True},
    )
    profile = store.get_interactive_profile("req-1")
    handle = store.get_engine_session_handle("req-1")
    sticky = store.get_sticky_wait_runtime("req-1")
    effective_timeout = store.get_effective_session_timeout("req-1")
    assert profile is not None
    assert profile["kind"] == "resumable"
    assert handle is not None
    assert handle["handle_value"] == "thread-1"
    assert sticky is not None
    assert sticky["wait_deadline_at"] == "2026-02-16T00:00:00"
    assert sticky["process_binding"]["alive"] is True
    assert effective_timeout == 1200


def test_get_request_by_run_id(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    store.create_request(
        request_id="req-1",
        skill_id="skill",
        engine="gemini",
        parameter={},
        engine_options={},
        runtime_options={"execution_mode": "interactive"},
        input_data={"foo": "bar"},
    )
    store.create_run("run-1", None, "queued")
    store.update_request_run_id("req-1", "run-1")
    request = store.get_request_by_run_id("run-1")
    assert request is not None
    assert request["request_id"] == "req-1"
    assert request["input"]["foo"] == "bar"


def test_interaction_history_and_consume_reply(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    store.set_pending_interaction(
        "req-1",
        {"interaction_id": 2, "kind": "choose_one", "prompt": "Pick one"},
    )
    store.append_interaction_history(
        request_id="req-1",
        interaction_id=2,
        event_type="ask_user",
        payload={"prompt": "Pick one"},
    )
    accepted = store.submit_interaction_reply(
        request_id="req-1",
        interaction_id=2,
        response={"answer": "a"},
        idempotency_key="k2",
    )
    consumed = store.consume_interaction_reply("req-1", 2)
    history = store.list_interaction_history("req-1")
    assert accepted == "accepted"
    assert consumed == {"answer": "a"}
    assert len(history) == 1
    assert history[0]["event_type"] == "ask_user"


def test_auto_decision_stats(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    store.append_interaction_history(
        request_id="req-1",
        interaction_id=1,
        event_type="reply",
        payload={
            "resolution_mode": "auto_decide_timeout",
            "resolved_at": "2026-02-16T00:00:01",
        },
    )
    store.append_interaction_history(
        request_id="req-1",
        interaction_id=2,
        event_type="reply",
        payload={
            "resolution_mode": "user_reply",
            "resolved_at": "2026-02-16T00:00:02",
        },
    )
    store.append_interaction_history(
        request_id="req-1",
        interaction_id=3,
        event_type="reply",
        payload={
            "resolution_mode": "auto_decide_timeout",
            "resolved_at": "2026-02-16T00:00:03",
        },
    )
    stats = store.get_auto_decision_stats("req-1")
    assert stats["auto_decision_count"] == 2
    assert stats["last_auto_decision_at"] == "2026-02-16T00:00:03"


def test_recovery_metadata_and_incomplete_scan_roundtrip(tmp_path):
    store = RunStore(db_path=tmp_path / "runs.db")
    store.create_request(
        request_id="req-1",
        skill_id="skill",
        engine="codex",
        parameter={},
        engine_options={},
        runtime_options={"execution_mode": "interactive"},
        input_data={},
    )
    store.create_run("run-1", None, "waiting_user")
    store.update_request_run_id("req-1", "run-1")
    store.set_interactive_profile(
        "req-1",
        {"kind": "resumable", "reason": "probe_ok", "session_timeout_sec": 1200},
    )
    store.set_engine_session_handle(
        "req-1",
        {
            "engine": "codex",
            "handle_type": "session_id",
            "handle_value": "thread-1",
            "created_at_turn": 1,
        },
    )
    store.set_sticky_wait_runtime(
        "req-1",
        "2099-01-01T00:00:00",
        {"run_id": "run-1", "alive": True},
    )
    store.set_recovery_info(
        "run-1",
        recovery_state="recovered_waiting",
        recovery_reason="resumable_waiting_preserved",
        recovered_at="2026-02-16T00:00:00",
    )

    info = store.get_recovery_info("run-1")
    assert info["recovery_state"] == "recovered_waiting"
    assert info["recovered_at"] == "2026-02-16T00:00:00"
    assert info["recovery_reason"] == "resumable_waiting_preserved"

    rows = store.list_incomplete_runs()
    assert len(rows) == 1
    assert rows[0]["run_status"] == "waiting_user"
    assert rows[0]["interactive_profile"]["kind"] == "resumable"
    assert rows[0]["session_handle"]["handle_value"] == "thread-1"

    store.clear_engine_session_handle("req-1")
    assert store.get_engine_session_handle("req-1") is None
    store.clear_sticky_wait_runtime("req-1")
    sticky = store.get_sticky_wait_runtime("req-1")
    assert sticky is not None
    assert sticky["wait_deadline_at"] is None
    assert sticky["process_binding"] is None
