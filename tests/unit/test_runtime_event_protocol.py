import json
from pathlib import Path

from server.services import runtime_event_protocol
from server.services.runtime_event_protocol import build_fcmp_events, build_rasp_events


def test_fcmp_suppresses_duplicate_raw_echo_blocks(tmp_path: Path):
    run_dir = tmp_path / "run"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    assistant = "\n".join(
        [
            "{",
            '  "x": 100,',
            '  "y": 50,',
            '  "__SKILL_DONE__": true',
            "}",
        ]
    )
    stderr_payload = {
        "session_id": "session-1",
        "response": assistant,
    }
    stdout_lines = [
        "YOLO mode is enabled.",
        "Loaded cached credentials.",
        "{",
        '"x": 100,',
        '"y": 50,',
        '"__SKILL_DONE__": true',
        "}",
    ]
    (logs_dir / "stdout.txt").write_text("\n".join(stdout_lines) + "\n", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text(
        json.dumps(stderr_payload, ensure_ascii=False),
        encoding="utf-8",
    )

    rasp_events = build_rasp_events(
        run_id="run-1",
        engine="gemini",
        attempt_number=1,
        status="succeeded",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
    )
    raw_rasp_lines = [
        event.data.get("line")
        for event in rasp_events
        if event.event.type in {"raw.stdout", "raw.stderr"}
    ]
    assert '"x": 100,' in raw_rasp_lines
    assert '"y": 50,' in raw_rasp_lines

    fcmp_events = build_fcmp_events(rasp_events, suppression_threshold=3)
    raw_fcmp_lines = [
        event.data.get("line")
        for event in fcmp_events
        if event.type in {"raw.stdout", "raw.stderr"}
    ]
    assert "YOLO mode is enabled." in raw_fcmp_lines
    assert "Loaded cached credentials." in raw_fcmp_lines
    assert '"x": 100,' not in raw_fcmp_lines
    assert '"y": 50,' not in raw_fcmp_lines
    assert len(raw_rasp_lines) > len(raw_fcmp_lines)

    suppression_diagnostics = [
        event
        for event in fcmp_events
        if event.type == "diagnostic.warning"
        and event.data.get("code") == "RAW_DUPLICATE_SUPPRESSED"
    ]
    assert suppression_diagnostics


def test_codex_parser_uses_pty_fallback_when_stdout_incomplete(tmp_path: Path):
    run_dir = tmp_path / "run-pty-fallback"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text('{"type":"thread.started","thread_id":"thread-pty"}\n', encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    pty_path = logs_dir / "pty-output.txt"
    pty_path.write_text(
        '{"type":"thread.started","thread_id":"thread-pty"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"from pty"}}\n'
        '{"type":"turn.completed"}\n',
        encoding="utf-8",
    )

    rasp_events = build_rasp_events(
        run_id="run-pty",
        engine="codex",
        attempt_number=1,
        status="succeeded",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
        pty_path=pty_path,
    )
    assert any(event.event.type == "agent.message.final" for event in rasp_events)
    assistant_event = next(event for event in rasp_events if event.event.type == "agent.message.final")
    assert assistant_event.data["text"] == "from pty"
    assert assistant_event.raw_ref is not None
    assert assistant_event.raw_ref.stream == "pty"
    assert any(
        event.event.type == "diagnostic.warning" and event.data.get("code") == "PTY_FALLBACK_USED"
        for event in rasp_events
    )


def test_completion_conflict_maps_to_failed_conversation(tmp_path: Path):
    run_dir = tmp_path / "run-conflict"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text(
        '{"type":"thread.started","thread_id":"thread-conflict"}\n'
        '{"type":"item.completed","item":{"type":"agent_message","text":"{\\"__SKILL_DONE__\\": true}"}}\n',
        encoding="utf-8",
    )
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")

    rasp_events = build_rasp_events(
        run_id="run-conflict",
        engine="codex",
        attempt_number=2,
        status="failed",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
        completion={
            "state": "interrupted",
            "reason_code": "PROCESS_EXIT_NONZERO",
            "diagnostics": ["DONE_MARKER_PROCESS_FAILURE_CONFLICT"],
        },
    )
    fcmp_events = build_fcmp_events(rasp_events)
    assert any(event.type == "conversation.failed" for event in fcmp_events)
    assert any(
        event.type == "diagnostic.warning"
        and event.data.get("code") == "DONE_MARKER_PROCESS_FAILURE_CONFLICT"
        for event in fcmp_events
    )


def test_build_rasp_events_delegates_parsing_to_adapter(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "run-delegate"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("raw stdout\n", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("raw stderr\n", encoding="utf-8")

    class _FakeAdapter:
        def parse_runtime_stream(self, *, stdout_raw: bytes, stderr_raw: bytes, pty_raw: bytes = b""):
            assert stdout_raw.decode("utf-8") == "raw stdout\n"
            assert stderr_raw.decode("utf-8") == "raw stderr\n"
            return {
                "parser": "fake_adapter_parser",
                "confidence": 0.93,
                "session_id": "sess-delegated",
                "assistant_messages": [{"text": "delegated message"}],
                "raw_rows": [],
                "diagnostics": ["DELEGATED_PARSE"],
                "structured_types": ["fake.type"],
            }

    monkeypatch.setattr(runtime_event_protocol.engine_adapter_registry, "get", lambda _engine: _FakeAdapter())
    events = build_rasp_events(
        run_id="run-delegate",
        engine="codex",
        attempt_number=1,
        status="succeeded",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
    )

    assert events
    assert all(event.source.parser == "fake_adapter_parser" for event in events)
    assert any(
        event.event.type == "agent.message.final" and event.data.get("text") == "delegated message"
        for event in events
    )
    assert any(
        event.event.type == "diagnostic.warning" and event.data.get("code") == "DELEGATED_PARSE"
        for event in events
    )


def test_soft_completion_reason_and_warning_propagate_to_fcmp(tmp_path: Path):
    run_dir = tmp_path / "run-soft-completion"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")

    rasp_events = build_rasp_events(
        run_id="run-soft-completion",
        engine="codex",
        attempt_number=1,
        status="succeeded",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
        completion={
            "state": "completed",
            "reason_code": "INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER",
            "diagnostics": ["INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER"],
        },
    )
    fcmp_events = build_fcmp_events(rasp_events)
    completed_event = next(event for event in fcmp_events if event.type == "conversation.completed")
    assert completed_event.data["reason_code"] == "INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER"
    assert any(
        event.type == "diagnostic.warning"
        and event.data.get("code") == "INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER"
        for event in fcmp_events
    )


def test_max_attempt_exceeded_maps_to_failed_conversation(tmp_path: Path):
    run_dir = tmp_path / "run-max-attempt-failed"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")

    rasp_events = build_rasp_events(
        run_id="run-max-attempt-failed",
        engine="codex",
        attempt_number=1,
        status="failed",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
        completion={
            "state": "interrupted",
            "reason_code": "INTERACTIVE_MAX_ATTEMPT_EXCEEDED",
            "diagnostics": ["INTERACTIVE_MAX_ATTEMPT_EXCEEDED"],
        },
    )
    fcmp_events = build_fcmp_events(rasp_events)
    failed_event = next(event for event in fcmp_events if event.type == "conversation.failed")
    assert failed_event.data["error"]["code"] == "INTERACTIVE_MAX_ATTEMPT_EXCEEDED"
    assert any(
        event.type == "diagnostic.warning"
        and event.data.get("code") == "INTERACTIVE_MAX_ATTEMPT_EXCEEDED"
        for event in fcmp_events
    )
