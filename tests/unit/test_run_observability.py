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
    (run_dir / "status.json").write_text(json.dumps({"status": "running", "updated_at": "2026-01-01T00:00:00"}), encoding="utf-8")

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


def test_get_logs_tail_waiting_user_sets_poll_false(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-waiting"
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs" / "stdout.txt").write_text("", encoding="utf-8")
    (run_dir / "logs" / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "waiting_user", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_request_with_run",
        lambda request_id: {
            "request_id": request_id,
            "run_id": "run-waiting",
            "skill_id": "demo",
            "engine": "gemini",
            "request_created_at": "2026-01-01T00:00:00",
            "run_status": "waiting_user",
        },
    )
    monkeypatch.setattr(
        "server.services.run_observability.workspace_manager.get_run_dir",
        lambda _run_id: run_dir,
    )

    service = RunObservabilityService()
    tail = service.get_logs_tail("req-waiting")
    assert tail["status"] == "waiting_user"
    assert tail["poll"] is False


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


@pytest.mark.asyncio
async def test_iter_sse_events_snapshot_stdout_stderr_and_terminal_end(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("hello", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("err", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "succeeded", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_pending_interaction",
        lambda _request_id: None,
    )

    service = RunObservabilityService()
    events = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-1",
        stdout_from=0,
        stderr_from=0,
        chunk_bytes=1024,
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        events.append(item)
        if item["event"] == "end":
            break

    assert events[0]["event"] == "snapshot"
    assert events[0]["data"]["status"] == "succeeded"
    assert any(evt["event"] == "stdout" and evt["data"]["chunk"] == "hello" for evt in events)
    assert any(evt["event"] == "stderr" and evt["data"]["chunk"] == "err" for evt in events)
    assert events[-1] == {"event": "end", "data": {"reason": "terminal"}}


@pytest.mark.asyncio
async def test_iter_sse_events_waiting_user_emits_status_and_end(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run"
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
        lambda _request_id: {"interaction_id": 7},
    )

    service = RunObservabilityService()
    events = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-wait",
        stdout_from=0,
        stderr_from=0,
        chunk_bytes=1024,
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        events.append(item)
        if item["event"] == "end":
            break

    assert events[0]["event"] == "snapshot"
    assert events[0]["data"]["pending_interaction_id"] == 7
    assert any(evt["event"] == "status" and evt["data"]["status"] == "waiting_user" for evt in events)
    assert events[-1] == {"event": "end", "data": {"reason": "waiting_user"}}


@pytest.mark.asyncio
async def test_iter_sse_events_waiting_user_emits_chat_events_before_end(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-wait-chat"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text(
        "\n".join(
            [
                '{"type":"thread.started","thread_id":"thread-wait"}',
                '{"type":"item.completed","item":{"type":"agent_message","text":"please provide info"}}',
                '{"type":"turn.completed"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "waiting_user", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_pending_interaction",
        lambda _request_id: {
            "interaction_id": 7,
            "kind": "open_text",
            "prompt": "请继续输入",
        },
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_request",
        lambda _request_id: {"engine": "codex", "runtime_options": {"execution_mode": "interactive"}},
    )
    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_interaction_count",
        lambda _request_id: 0,
    )

    service = RunObservabilityService()
    events = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-wait-chat",
        stdout_from=0,
        stderr_from=0,
        chunk_bytes=1024,
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        events.append(item)
        if item["event"] == "end":
            break

    chat_events = [evt for evt in events if evt["event"] == "chat_event"]
    assert chat_events
    assert any(evt["data"]["type"] == "assistant.message.final" for evt in chat_events)
    assert any(evt["data"]["type"] == "user.input.required" for evt in chat_events)
    assert events[-1] == {"event": "end", "data": {"reason": "waiting_user"}}


@pytest.mark.asyncio
async def test_iter_sse_events_respects_reconnect_offsets(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("hello-world", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "succeeded", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_pending_interaction",
        lambda _request_id: None,
    )

    service = RunObservabilityService()
    events = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-offset",
        stdout_from=5,
        stderr_from=0,
        chunk_bytes=1024,
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        events.append(item)
        if item["event"] == "end":
            break

    stdout_events = [evt for evt in events if evt["event"] == "stdout"]
    assert len(stdout_events) == 1
    assert stdout_events[0]["data"]["from"] == 5
    assert stdout_events[0]["data"]["chunk"] == "-world"


@pytest.mark.asyncio
async def test_iter_sse_events_canceled_status_contains_error_code(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps(
            {
                "status": "canceled",
                "updated_at": "2026-01-01T00:00:00",
                "error": {"code": "CANCELED_BY_USER", "message": "Canceled by user request"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_pending_interaction",
        lambda _request_id: None,
    )

    service = RunObservabilityService()
    events = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-cancel",
        stdout_from=0,
        stderr_from=0,
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        events.append(item)
        if item["event"] == "end":
            break

    status_events = [evt for evt in events if evt["event"] == "status"]
    assert status_events
    assert status_events[-1]["data"]["status"] == "canceled"
    assert status_events[-1]["data"]["error_code"] == "CANCELED_BY_USER"


@pytest.mark.asyncio
async def test_iter_sse_events_emits_run_event_and_chat_event(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-protocol"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_lines = [
        '{"type":"thread.started","thread_id":"thread-1"}',
        '{"type":"item.completed","item":{"type":"agent_message","text":"hello from codex"}}',
        "not-json-line",
    ]
    (logs_dir / "stdout.txt").write_text("\n".join(stdout_lines) + "\n", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "succeeded", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_pending_interaction",
        lambda _request_id: None,
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
    events = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-protocol",
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        events.append(item)
        if item["event"] == "end":
            break

    run_events = [evt for evt in events if evt["event"] == "run_event"]
    chat_events = [evt for evt in events if evt["event"] == "chat_event"]
    assert run_events
    assert run_events[0]["data"]["protocol_version"] == "rasp/1.0"
    assert any(evt["data"]["event"]["type"] == "agent.message.final" for evt in run_events)
    assert any(evt["data"]["event"]["type"] == "raw.stdout" for evt in run_events)
    assert any(evt["data"]["event"]["type"] == "diagnostic.warning" for evt in run_events)

    assert chat_events
    assert chat_events[0]["data"]["protocol_version"] == "fcmp/1.0"
    assert any(evt["data"]["type"] == "assistant.message.final" for evt in chat_events)
    assert any(evt["data"]["type"] == "conversation.completed" for evt in chat_events)

    audit_dir = run_dir / ".audit"
    assert (audit_dir / "events.jsonl").exists()
    assert (audit_dir / "parser_diagnostics.jsonl").exists()


@pytest.mark.asyncio
async def test_iter_sse_events_cursor_skips_old_run_events(monkeypatch, tmp_path: Path):
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

    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_pending_interaction",
        lambda _request_id: None,
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
    first_pass = []
    async for item in service.iter_sse_events(
        run_dir=run_dir,
        request_id="req-cursor",
        poll_interval_sec=0.01,
        heartbeat_interval_sec=1.0,
    ):
        first_pass.append(item)
        if item["event"] == "end":
            break
    max_seq = max(
        evt["data"]["seq"]
        for evt in first_pass
        if evt["event"] == "run_event"
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
        if item["event"] == "end":
            break
    second_run_events = [evt for evt in second_pass if evt["event"] == "run_event"]
    assert second_run_events == []


def test_list_event_history_filters_by_seq(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-history"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text(
        '{"type":"thread.started","thread_id":"thread-h"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"hello"}}\n'
        "noise\n",
        encoding="utf-8",
    )
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    (run_dir / "status.json").write_text(
        json.dumps({"status": "succeeded", "updated_at": "2026-01-01T00:00:00"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "server.services.run_observability.run_store.get_pending_interaction",
        lambda _request_id: None,
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
    rows = service.list_event_history(
        run_dir=run_dir,
        request_id="req-history",
        from_seq=2,
        to_seq=3,
    )
    assert rows
    assert all(2 <= row["seq"] <= 3 for row in rows)

    metrics_path = run_dir / ".audit" / "protocol_metrics.json"
    assert metrics_path.exists()
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["event_count"] >= 1
    assert metrics["parser_profile"] == "codex_ndjson"


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
