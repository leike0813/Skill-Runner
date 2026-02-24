import json
from pathlib import Path

import pytest

from server.services.run_observability import RunObservabilityService


def test_list_runs_and_get_logs_tail(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-1"
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs" / "stdout.txt").write_text("line1\nline2\n", encoding="utf-8")
    (run_dir / "logs" / "stderr.txt").write_text("err1\n", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "running", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "server.services.run_observability.run_store.list_requests_with_runs",
        lambda limit=200: [
            {
                "request_id": "req-1",
                "run_id": "run-1",
                "skill_id": "demo",
                "engine": "gemini",
                "request_created_at": "2026-01-01T00:00:00",
                "run_status": "running",
            }
        ],
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_request_with_run",
        lambda request_id: {
            "request_id": request_id,
            "run_id": "run-1",
            "skill_id": "demo",
            "engine": "gemini",
            "request_created_at": "2026-01-01T00:00:00",
            "run_status": "running",
        },
    )
    monkeypatch.setattr(
        "server.services.run_observability.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )

    service = RunObservabilityService()
    rows = service.list_runs()
    assert len(rows) == 1
    assert rows[0]["request_id"] == "req-1"
    assert rows[0]["status"] == "running"

    tail = service.get_logs_tail("req-1", max_bytes=5)
    assert tail["poll"] is True
    assert tail["stdout"].endswith("ne2\n")
    assert "err1" in tail["stderr"]


def test_read_log_increment_supports_offsets_and_chunking(tmp_path: Path):
    log_path = tmp_path / "stdout.txt"
    log_path.write_text("abcdef", encoding="utf-8")
    service = RunObservabilityService()

    chunk1 = service.read_log_increment(log_path, from_offset=0, max_bytes=2)
    assert chunk1 == {"from": 0, "to": 2, "chunk": "ab"}

    chunk2 = service.read_log_increment(log_path, from_offset=2, max_bytes=3)
    assert chunk2 == {"from": 2, "to": 5, "chunk": "cde"}

    chunk3 = service.read_log_increment(log_path, from_offset=5, max_bytes=3)
    assert chunk3 == {"from": 5, "to": 6, "chunk": "f"}


def test_list_event_history_filters_invalid_fcmp_rows(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-history"
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    fcmp_path = audit_dir / "fcmp_events.jsonl"
    fcmp_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "protocol_version": "fcmp/1.0",
                        "run_id": "run-history",
                        "seq": 1,
                        "ts": "2026-02-24T00:00:00",
                        "engine": "codex",
                        "type": "conversation.state.changed",
                        "data": {
                            "from": "queued",
                            "to": "running",
                            "trigger": "turn.started",
                            "updated_at": "2026-02-24T00:00:00",
                            "pending_interaction_id": None,
                        },
                        "meta": {"attempt": 1},
                    }
                ),
                json.dumps(
                    {
                        "protocol_version": "fcmp/1.0",
                        "run_id": "run-history",
                        "seq": 2,
                        "ts": "2026-02-24T00:00:01",
                        "engine": "codex",
                        "type": "conversation.state.changed",
                        "data": {"to": "running"},
                        "meta": {"attempt": 1},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "server.services.run_observability.RunObservabilityService._materialize_protocol_stream",
        lambda self, **_kwargs: {"rasp_events": [], "fcmp_events": []},
    )
    monkeypatch.setattr(
        "server.services.run_observability.RunObservabilityService._read_status_payload",
        lambda self, _run_dir: {"status": "succeeded"},
    )
    service = RunObservabilityService()
    rows = service.list_event_history(run_dir=run_dir, request_id="req-hist")
    assert len(rows) == 1
    assert rows[0]["seq"] == 1


def _patch_protocol_defaults(monkeypatch, *, status: str, execution_mode: str = "auto") -> None:
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_pending_interaction",
        lambda _request_id: None,
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_request",
        lambda _request_id: {"engine": "codex", "runtime_options": {"execution_mode": execution_mode}},
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_interaction_count",
        lambda _request_id: 0,
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.list_interaction_history",
        lambda _request_id: [],
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_effective_session_timeout",
        lambda _request_id: 1200,
    )
    _ = status


@pytest.mark.asyncio
async def test_iter_sse_events_chat_only_for_terminal_status(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-protocol"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text(
        '{"type":"thread.started","thread_id":"thread-1"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"hello from codex"}}\n',
        encoding="utf-8",
    )
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "succeeded", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )
    _patch_protocol_defaults(monkeypatch, status="succeeded")

    service = RunObservabilityService()
    events = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-protocol",
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        events.append(item)

    assert events
    assert events[0]["event"] == "snapshot"
    event_names = {item["event"] for item in events}
    assert "chat_event" in event_names
    assert event_names.isdisjoint({"run_event", "status", "stdout", "stderr", "end"})

    chat_events = [evt["data"] for evt in events if evt["event"] == "chat_event"]
    assert any(evt["type"] == "assistant.message.final" for evt in chat_events)
    assert any(evt["type"] == "conversation.completed" for evt in chat_events)
    assert any(
        evt["type"] == "conversation.state.changed" and evt["data"].get("to") == "succeeded"
        for evt in chat_events
    )


@pytest.mark.asyncio
async def test_iter_sse_events_waiting_user_chat_only(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-wait"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "waiting_user", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_pending_interaction",
        lambda _request_id: {"interaction_id": 7, "kind": "open_text", "prompt": "请继续输入"},
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_request",
        lambda _request_id: {"engine": "codex", "runtime_options": {"execution_mode": "interactive"}},
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_interaction_count",
        lambda _request_id: 0,
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.list_interaction_history",
        lambda _request_id: [],
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_effective_session_timeout",
        lambda _request_id: 1200,
    )

    service = RunObservabilityService()
    events = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-wait",
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        events.append(item)

    assert events[0]["event"] == "snapshot"
    assert events[0]["data"]["pending_interaction_id"] == 7
    assert all(evt["event"] != "end" for evt in events)
    chat_events = [evt["data"] for evt in events if evt["event"] == "chat_event"]
    assert any(evt["type"] == "user.input.required" for evt in chat_events)
    assert any(
        evt["type"] == "conversation.state.changed" and evt["data"].get("to") == "waiting_user"
        for evt in chat_events
    )


@pytest.mark.asyncio
async def test_iter_sse_events_cursor_skips_old_chat_events(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-cursor"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text(
        '{"type":"thread.started","thread_id":"thread-2"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"first"}}\n',
        encoding="utf-8",
    )
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "succeeded", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )
    _patch_protocol_defaults(monkeypatch, status="succeeded")

    service = RunObservabilityService()
    first_pass = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-cursor",
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        first_pass.append(item)
    max_seq = max(
        evt["data"]["seq"]
        for evt in first_pass
        if evt["event"] == "chat_event"
    )

    second_pass = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-cursor",
        cursor=max_seq,
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        second_pass.append(item)
    second_chat_events = [evt for evt in second_pass if evt["event"] == "chat_event"]
    assert second_chat_events == []


def test_list_event_history_filters_fcmp_by_seq(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-history"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text(
        '{"type":"thread.started","thread_id":"thread-h"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"hello"}}\n',
        encoding="utf-8",
    )
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "succeeded", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )
    _patch_protocol_defaults(monkeypatch, status="succeeded")

    service = RunObservabilityService()
    rows = service.list_event_history(
        run_dir=run_dir,
        request_id="req-history",
        from_seq=2,
        to_seq=4,
    )
    assert rows
    assert all(2 <= row["seq"] <= 4 for row in rows)
    assert all(row["protocol_version"] == "fcmp/1.0" for row in rows)

    metrics_path = run_dir / ".audit" / "protocol_metrics.json"
    assert metrics_path.exists()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["event_count"] >= 1


def test_read_log_range_prefers_attempt_logs(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-range"
    logs_dir = run_dir / "logs"
    audit_dir = run_dir / ".audit"
    logs_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(
        json.dumps({"status": "succeeded", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )
    (logs_dir / "stdout.txt").write_text("live-stdout", encoding="utf-8")
    (audit_dir / "stdout.1.log").write_text("audit-stdout", encoding="utf-8")
    (audit_dir / "meta.1.json").write_text(
        json.dumps({"completion": {"state": "completed", "reason_code": "DONE_MARKER_FOUND"}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_request",
        lambda _request_id: {"engine": "codex", "runtime_options": {"execution_mode": "auto"}},
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_interaction_count",
        lambda _request_id: 0,
    )

    service = RunObservabilityService()
    payload = service.read_log_range(
        run_dir=run_dir,
        request_id="req-range",
        stream="stdout",
        byte_from=0,
        byte_to=5,
    )
    assert payload["chunk"] == "audit"
