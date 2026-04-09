import json
from pathlib import Path

import pytest

from server.runtime.protocol import event_protocol as runtime_event_protocol
from server.runtime.protocol.event_protocol import (
    build_fcmp_events,
    build_rasp_events,
    read_jsonl,
    translate_orchestrator_event_to_fcmp_specs,
)
from server.runtime.protocol.schema_registry import (
    ProtocolSchemaViolation,
    validate_fcmp_event,
    validate_rasp_event,
)


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
    assert '"x": 100,' not in raw_rasp_lines
    assert '"y": 50,' not in raw_rasp_lines

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
    assert len(raw_rasp_lines) == len(raw_fcmp_lines)

    suppression_diagnostics = [
        event
        for event in fcmp_events
        if event.type == "diagnostic.warning"
        and event.data.get("code") == "RAW_DUPLICATE_SUPPRESSED"
    ]
    assert not suppression_diagnostics


def test_build_rasp_events_coalesces_large_stderr_bursts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-coalesced"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    stderr_lines = [f"gemini overload retry line {idx}" for idx in range(260)]
    (logs_dir / "stderr.txt").write_text("\n".join(stderr_lines) + "\n", encoding="utf-8")

    rasp_events = build_rasp_events(
        run_id="run-coalesced",
        engine="unknown",
        attempt_number=1,
        status="failed",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
    )

    raw_stderr_events = [event for event in rasp_events if event.event.type == "raw.stderr"]
    assert len(raw_stderr_events) < 260
    assert any("\n" in str(event.data.get("line", "")) for event in raw_stderr_events)
    assert any(
        event.event.type == "diagnostic.warning" and event.data.get("code") == "RAW_STDERR_COALESCED"
        for event in rasp_events
    )


def test_build_rasp_events_coalesces_pretty_json_blocks_below_min_threshold(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-pretty-json"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text(
        "\n".join(
            [
                "prefix warning",
                "{",
                '  "error": {',
                '    "code": 429,',
                '    "message": "rate limit"',
                "  },",
                '  "retry_after": 12',
                "}",
                "suffix warning",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rasp_events = build_rasp_events(
        run_id="run-pretty-json",
        engine="unknown",
        attempt_number=1,
        status="failed",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
    )

    raw_stderr_lines = [
        str(event.data.get("line", ""))
        for event in rasp_events
        if event.event.type == "raw.stderr"
    ]
    assert len(raw_stderr_lines) == 3
    assert raw_stderr_lines[1].startswith("{\n")
    assert '"retry_after": 12' in raw_stderr_lines[1]


def test_read_jsonl_recovers_concatenated_json_objects_on_single_line(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"seq":1,"event":{"type":"raw.stderr"}}{"seq":2,"event":{"type":"diagnostic.warning"}}\n',
        encoding="utf-8",
    )
    rows = read_jsonl(path)
    assert len(rows) == 2
    assert rows[0]["seq"] == 1
    assert rows[1]["seq"] == 2


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


def test_process_events_promote_to_final_on_turn_completed(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-promote-turn-end"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text(
        "\n".join(
            [
                '{"type":"thread.started","thread_id":"thread-promote"}',
                '{"type":"turn.started"}',
                '{"type":"item.completed","item":{"id":"msg-1","type":"agent_message","text":"step message"}}',
                '{"type":"turn.completed"}',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")

    rasp_events = build_rasp_events(
        run_id="run-promote-turn-end",
        engine="codex",
        attempt_number=1,
        status="running",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
    )

    types = [event.event.type for event in rasp_events]
    assert "agent.message.intermediate" in types
    assert "agent.message.promoted" in types
    assert "agent.message.final" in types
    assert types.index("agent.message.promoted") < types.index("agent.message.final")

    fcmp_events = build_fcmp_events(rasp_events, status="running")
    fcmp_types = [event.type for event in fcmp_events]
    assert "assistant.message.intermediate" in fcmp_types
    assert "assistant.message.promoted" in fcmp_types
    assert "assistant.message.final" in fcmp_types


def test_turn_markers_are_rasp_only_and_not_mapped_to_fcmp(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-turn-markers"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text(
        "\n".join(
            [
                '{"type":"thread.started","thread_id":"thread-1"}',
                '{"type":"turn.started"}',
                '{"type":"item.completed","item":{"id":"msg-1","type":"agent_message","text":"step message"}}',
                '{"type":"turn.completed","usage":{"input_tokens":11,"output_tokens":3}}',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")

    rasp_events = build_rasp_events(
        run_id="run-turn-markers",
        engine="codex",
        attempt_number=1,
        status="running",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
    )
    rasp_types = [event.event.type for event in rasp_events]
    assert "lifecycle.run_handle" in rasp_types
    assert "agent.turn_start" in rasp_types
    assert "agent.turn_complete" in rasp_types
    run_handle_event = next(event for event in rasp_events if event.event.type == "lifecycle.run_handle")
    assert run_handle_event.data.get("handle_id") == "thread-1"
    turn_complete_event = next(event for event in rasp_events if event.event.type == "agent.turn_complete")
    assert turn_complete_event.data.get("input_tokens") == 11
    assert turn_complete_event.data.get("output_tokens") == 3
    assert rasp_types.index("agent.turn_start") < rasp_types.index("agent.turn_complete")

    fcmp_events = build_fcmp_events(rasp_events, status="running")
    fcmp_types = [event.type for event in fcmp_events]
    assert not any(type_name.startswith("assistant.turn") for type_name in fcmp_types)


def test_no_fallback_final_on_failed_without_turn_completed(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-no-fallback-final"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text(
        "\n".join(
            [
                '{"type":"thread.started","thread_id":"thread-failed"}',
                '{"type":"item.completed","item":{"id":"msg-fail","type":"agent_message","text":"intermediate"}}',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")

    rasp_events = build_rasp_events(
        run_id="run-no-fallback-final",
        engine="codex",
        attempt_number=1,
        status="failed",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
    )
    types = [event.event.type for event in rasp_events]
    assert "agent.message.intermediate" in types
    assert "agent.message.final" not in types


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
    terminal_event = next(
        event
        for event in fcmp_events
        if event.type == "conversation.state.changed" and event.data.get("to") == "failed"
    )
    assert terminal_event.data["terminal"]["status"] == "failed"
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
            assert stdout_raw.decode("utf-8").replace("\r\n", "\n") == "raw stdout\n"
            assert stderr_raw.decode("utf-8").replace("\r\n", "\n") == "raw stderr\n"
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
    intermediate_event = next(event for event in events if event.event.type == "agent.message.intermediate")
    final_event = next(event for event in events if event.event.type == "agent.message.final")
    assert intermediate_event.data["message_id"] == final_event.data["message_id"]
    assert final_event.data["replaces_message_id"] == intermediate_event.data["message_id"]
    assert any(
        event.event.type == "agent.message.final" and event.data.get("text") == "delegated message"
        for event in events
    )
    assert any(
        event.event.type == "diagnostic.warning" and event.data.get("code") == "DELEGATED_PARSE"
        for event in events
    )


def test_build_rasp_events_emits_parsed_json_from_structured_payload(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "run-parsed-json"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("{}", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")

    class _FakeAdapter:
        def parse_runtime_stream(self, *, stdout_raw: bytes, stderr_raw: bytes, pty_raw: bytes = b""):
            return {
                "parser": "gemini_json",
                "confidence": 0.9,
                "session_id": "sess-structured",
                "assistant_messages": [],
                "raw_rows": [],
                "diagnostics": [],
                "structured_types": ["gemini.stream_response"],
                "structured_payloads": [
                    {
                        "type": "parsed.json",
                        "stream": "stdout",
                        "session_id": "sess-structured",
                        "response": "hello",
                        "summary": "hello",
                        "details": {"stats": {"ok": True}},
                        "raw_ref": {"stream": "stdout", "byte_from": 0, "byte_to": 32},
                    }
                ],
            }

    monkeypatch.setattr(runtime_event_protocol.engine_adapter_registry, "get", lambda _engine: _FakeAdapter())

    rasp_events = build_rasp_events(
        run_id="run-parsed-json",
        engine="gemini",
        attempt_number=1,
        status="succeeded",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
    )
    parsed_event = next(event for event in rasp_events if event.event.type == "parsed.json")
    assert parsed_event.data["stream"] == "stdout"
    assert parsed_event.data["session_id"] == "sess-structured"
    assert parsed_event.data["response"] == "hello"
    assert isinstance(parsed_event.data.get("details"), dict)


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
    completed_event = next(
        event
        for event in fcmp_events
        if event.type == "conversation.state.changed" and event.data.get("to") == "succeeded"
    )
    assert completed_event.data["terminal"]["reason_code"] == "INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER"
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
    failed_event = next(
        event
        for event in fcmp_events
        if event.type == "conversation.state.changed" and event.data.get("to") == "failed"
    )
    assert failed_event.data["terminal"]["error"]["code"] == "INTERACTIVE_MAX_ATTEMPT_EXCEEDED"
    assert any(
        event.type == "diagnostic.warning"
        and event.data.get("code") == "INTERACTIVE_MAX_ATTEMPT_EXCEEDED"
        for event in fcmp_events
    )


def test_completed_completion_does_not_override_failed_terminal_status(tmp_path: Path):
    run_dir = tmp_path / "run-completion-conflict"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")

    rasp_events = build_rasp_events(
        run_id="run-completion-conflict",
        engine="codex",
        attempt_number=1,
        status="failed",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
        completion={
            "state": "completed",
            "reason_code": "DONE_MARKER_FOUND",
            "diagnostics": [],
        },
    )
    fcmp_events = build_fcmp_events(rasp_events)

    failed_event = next(
        event
        for event in fcmp_events
        if event.type == "conversation.state.changed" and event.data.get("to") == "failed"
    )
    assert failed_event.data["terminal"]["status"] == "failed"
    assert not any(
        event.type == "conversation.state.changed" and event.data.get("to") == "succeeded"
        for event in fcmp_events
    )
    assert any(
        event.type == "diagnostic.warning"
        and event.data.get("code") == "TERMINAL_STATUS_COMPLETION_CONFLICT"
        for event in fcmp_events
    )


def test_fcmp_emits_state_changed_for_waiting_user(tmp_path: Path):
    run_dir = tmp_path / "run-state-wait"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    pending = {"interaction_id": 8, "kind": "open_text", "prompt": "next step"}

    rasp_events = build_rasp_events(
        run_id="run-state-wait",
        engine="codex",
        attempt_number=1,
        status="waiting_user",
        pending_interaction=pending,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
    )
    fcmp_events = build_fcmp_events(
        rasp_events,
        status="waiting_user",
        status_updated_at="2026-02-24T00:00:00",
        pending_interaction=pending,
    )
    assert any(
        event.type == "conversation.state.changed" and event.data.get("to") == "waiting_user"
        for event in fcmp_events
    )
    user_required = next(event for event in fcmp_events if event.type == "user.input.required")
    assert user_required.data.get("prompt") == "next step"
    assert user_required.data.get("prompt") != "Provide next user turn"


def test_fcmp_emits_auth_required_and_waiting_auth_transition(tmp_path: Path):
    run_dir = tmp_path / "run-state-auth"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    pending_auth = {
        "auth_session_id": "auth-1",
        "engine": "opencode",
        "provider_id": "deepseek",
        "auth_method": "api_key",
        "challenge_kind": "api_key",
        "prompt": "Authentication is required.",
        "auth_url": None,
        "user_code": None,
        "instructions": "Paste API key into chat.",
        "accepts_chat_input": True,
        "input_kind": "api_key",
        "last_error": None,
        "source_attempt": 1,
        "phase": "challenge_active",
        "timeout_sec": 900,
        "created_at": "2026-03-03T00:00:00Z",
        "expires_at": "2026-03-03T00:15:00Z",
    }

    rasp_events = build_rasp_events(
        run_id="run-state-auth",
        engine="opencode",
        attempt_number=1,
        status="waiting_auth",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
        completion={"state": "awaiting_auth", "reason_code": "WAITING_AUTH_REQUIRED", "diagnostics": []},
    )
    fcmp_events = build_fcmp_events(
        rasp_events,
        status="waiting_auth",
        status_updated_at="2026-02-24T00:00:00",
        pending_auth=pending_auth,
        orchestrator_events=[
            {
                "ts": "2026-02-24T00:00:00",
                "attempt_number": 1,
                "seq": 1,
                "category": "interaction",
                "type": "auth.session.created",
                "data": pending_auth,
            }
        ],
    )

    auth_required = next(event for event in fcmp_events if event.type == "auth.required")
    assert auth_required.data["auth_session_id"] == "auth-1"
    assert auth_required.data["provider_id"] == "deepseek"
    assert auth_required.data["phase"] == "challenge_active"
    state_changed = next(
        event
        for event in fcmp_events
        if event.type == "conversation.state.changed" and event.data.get("to") == "waiting_auth"
    )
    assert state_changed.data["trigger"] == "auth.required"
    assert state_changed.data["pending_auth_session_id"] == "auth-1"


def test_fcmp_emits_auth_required_for_custom_provider_challenge(tmp_path: Path):
    run_dir = tmp_path / "run-state-auth-custom-provider"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    pending_auth = {
        "auth_session_id": "provider-config::req-1",
        "engine": "claude",
        "provider_id": "openrouter",
        "auth_method": "custom_provider",
        "challenge_kind": "custom_provider",
        "prompt": "Configure provider settings in chat.",
        "auth_url": None,
        "user_code": None,
        "instructions": "Submit provider_id, api_key, base_url, and model JSON.",
        "accepts_chat_input": True,
        "input_kind": "custom_provider",
        "last_error": None,
        "source_attempt": 1,
        "phase": "challenge_active",
    }

    rasp_events = build_rasp_events(
        run_id="run-state-auth-custom-provider",
        engine="claude",
        attempt_number=1,
        status="waiting_auth",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
        completion={"state": "awaiting_auth", "reason_code": "WAITING_AUTH_REQUIRED", "diagnostics": []},
    )
    fcmp_events = build_fcmp_events(
        rasp_events,
        status="waiting_auth",
        status_updated_at="2026-03-04T00:00:00",
        pending_auth=pending_auth,
        orchestrator_events=[
            {
                "ts": "2026-03-04T00:00:00",
                "attempt_number": 1,
                "seq": 1,
                "category": "interaction",
                "type": "auth.session.created",
                "data": pending_auth,
            }
        ],
    )

    auth_required = next(event for event in fcmp_events if event.type == "auth.required")
    assert auth_required.data["provider_id"] == "openrouter"
    assert auth_required.data["auth_method"] == "custom_provider"
    assert auth_required.data["challenge_kind"] == "custom_provider"


def test_fcmp_auth_required_prefers_pending_auth_provider_when_orchestrator_payload_is_missing_it(tmp_path: Path):
    run_dir = tmp_path / "run-state-auth-fallback-provider"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    pending_auth = {
        "auth_session_id": "auth-1",
        "engine": "opencode",
        "provider_id": "deepseek",
        "auth_method": "api_key",
        "challenge_kind": "api_key",
        "prompt": "Authentication is required.",
        "auth_url": None,
        "user_code": None,
        "instructions": "Paste API key into chat.",
        "accepts_chat_input": True,
        "input_kind": "api_key",
        "last_error": None,
        "source_attempt": 1,
        "phase": "challenge_active",
        "timeout_sec": 900,
        "created_at": "2026-03-03T00:00:00Z",
        "expires_at": "2026-03-03T00:15:00Z",
    }

    rasp_events = build_rasp_events(
        run_id="run-state-auth-fallback-provider",
        engine="opencode",
        attempt_number=1,
        status="waiting_auth",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
        completion={"state": "awaiting_auth", "reason_code": "WAITING_AUTH_REQUIRED", "diagnostics": []},
    )
    fcmp_events = build_fcmp_events(
        rasp_events,
        status="waiting_auth",
        status_updated_at="2026-02-24T00:00:00",
        pending_auth=pending_auth,
        orchestrator_events=[
            {
                "ts": "2026-02-24T00:00:00",
                "attempt_number": 1,
                "seq": 1,
                "category": "interaction",
                "type": "auth.session.created",
                "data": {
                    "auth_session_id": "auth-1",
                    "engine": "opencode",
                    "provider_id": None,
                    "phase": "challenge_active",
                },
            }
        ],
    )

    auth_required = next(event for event in fcmp_events if event.type == "auth.required")
    assert auth_required.data["provider_id"] == "deepseek"


def test_fcmp_emits_auth_required_for_method_selection(tmp_path: Path):
    run_dir = tmp_path / "run-auth-selection"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    pending_selection = {
        "engine": "codex",
        "provider_id": None,
        "available_methods": ["callback", "device_auth"],
        "prompt": "Authentication is required. Choose how to continue.",
        "instructions": "Select an authentication method to continue.",
        "last_error": None,
        "source_attempt": 1,
        "phase": "method_selection",
        "ui_hints": {"widget": "choice"},
    }

    rasp_events = build_rasp_events(
        run_id="run-auth-selection",
        engine="codex",
        attempt_number=1,
        status="waiting_auth",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
        completion={"state": "awaiting_auth", "reason_code": "WAITING_AUTH_REQUIRED", "diagnostics": []},
    )
    fcmp_events = build_fcmp_events(
        rasp_events,
        status="waiting_auth",
        status_updated_at="2026-03-03T00:00:00",
        pending_auth_method_selection=pending_selection,
        orchestrator_events=[
            {
                "ts": "2026-03-03T00:00:00",
                "attempt_number": 1,
                "seq": 1,
                "category": "interaction",
                "type": "auth.method.selection.required",
                "data": pending_selection,
            }
        ],
    )

    auth_required = next(event for event in fcmp_events if event.type == "auth.required")
    assert auth_required.data["phase"] == "method_selection"
    assert auth_required.data["available_methods"] == ["callback", "device_auth"]
    state_changed = next(
        event
        for event in fcmp_events
        if event.type == "conversation.state.changed" and event.data.get("to") == "waiting_auth"
    )
    assert state_changed.data["pending_auth_session_id"] is None


def test_fcmp_waiting_auth_suppresses_process_exit_failed_event(tmp_path: Path):
    run_dir = tmp_path / "run-auth-selection-no-fail"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    pending_selection = {
        "engine": "codex",
        "provider_id": None,
        "available_methods": ["callback", "device_auth"],
        "prompt": "Authentication is required. Choose how to continue.",
        "instructions": "Select an authentication method to continue.",
        "last_error": None,
        "source_attempt": 1,
        "phase": "method_selection",
        "ui_hints": {"widget": "choice"},
    }

    rasp_events = build_rasp_events(
        run_id="run-auth-selection-no-fail",
        engine="codex",
        attempt_number=1,
        status="waiting_auth",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
        completion={"state": "interrupted", "reason_code": "PROCESS_EXIT_NONZERO", "diagnostics": []},
    )
    fcmp_events = build_fcmp_events(
        rasp_events,
        status="waiting_auth",
        status_updated_at="2026-03-03T00:00:00",
        pending_auth_method_selection=pending_selection,
        orchestrator_events=[
            {
                "ts": "2026-03-03T00:00:00",
                "attempt_number": 1,
                "seq": 1,
                "category": "interaction",
                "type": "auth.method.selection.required",
                "data": pending_selection,
            }
        ],
    )

    assert any(event.type == "auth.required" for event in fcmp_events)
    assert not any(
        event.type == "conversation.state.changed" and event.data.get("to") == "failed"
        for event in fcmp_events
    )


def test_fcmp_emits_auth_completion_transition(tmp_path: Path):
    run_dir = tmp_path / "run-auth-completed"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")

    rasp_events = build_rasp_events(
        run_id="run-auth-completed",
        engine="opencode",
        attempt_number=1,
        status="queued",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
    )
    fcmp_events = build_fcmp_events(
        rasp_events,
        status="queued",
        status_updated_at="2026-02-24T00:00:01",
        orchestrator_events=[
            {
                "ts": "2026-02-24T00:00:01",
                "attempt_number": 1,
                "seq": 2,
                "category": "interaction",
                "type": "auth.session.completed",
                "data": {
                    "auth_session_id": "auth-1",
                    "resume_attempt": 2,
                    "source_attempt": 1,
                    "target_attempt": 2,
                    "resume_ticket_id": "ticket-1",
                    "ticket_consumed": True,
                    "completed_at": "2026-02-24T00:00:01Z",
                },
            }
        ],
    )

    auth_completed = next(event for event in fcmp_events if event.type == "auth.completed")
    assert auth_completed.data["auth_session_id"] == "auth-1"
    state_changed = next(
        event
        for event in fcmp_events
        if event.type == "conversation.state.changed" and event.data.get("from") == "waiting_auth"
    )
    assert state_changed.data["to"] == "queued"
    assert state_changed.data["trigger"] == "auth.completed"


def test_translate_orchestrator_interaction_reply_accepted_to_fcmp_pair() -> None:
    specs = translate_orchestrator_event_to_fcmp_specs(
        engine="gemini",
        type_name="interaction.reply.accepted",
        data={
            "interaction_id": 7,
            "resolution_mode": "user_reply",
            "accepted_at": "2026-03-04T00:00:05Z",
            "response_preview": "男，38，程序员",
        },
        updated_at="2026-03-04T00:00:05Z",
        default_attempt_number=2,
    )

    assert [spec["type_name"] for spec in specs] == [
        "interaction.reply.accepted",
        "conversation.state.changed",
    ]
    accepted = specs[0]["data"]
    assert accepted["interaction_id"] == 7
    assert accepted["resolution_mode"] == "user_reply"
    assert accepted["response_preview"] == "男，38，程序员"
    state_changed = specs[1]["data"]
    assert state_changed["from"] == "waiting_user"
    assert state_changed["to"] == "queued"
    assert state_changed["trigger"] == "interaction.reply.accepted"
    assert state_changed["pending_owner"] == "waiting_user"
    assert state_changed["resume_cause"] == "interaction_reply"


def test_translate_orchestrator_terminal_failed_carries_error_summary() -> None:
    specs = translate_orchestrator_event_to_fcmp_specs(
        engine="codex",
        type_name="lifecycle.run.terminal",
        data={
            "status": "failed",
            "code": "SCHEMA_VALIDATION_FAILED",
            "message": "Missing required artifacts: report.md",
        },
        updated_at="2026-03-07T00:00:00Z",
        default_attempt_number=1,
    )
    assert len(specs) == 1
    payload = specs[0]["data"]
    assert payload["to"] == "failed"
    assert payload["terminal"]["error"]["code"] == "SCHEMA_VALIDATION_FAILED"
    assert payload["terminal"]["error"]["message"] == "Missing required artifacts: report.md"


def test_build_fcmp_events_uses_orchestrator_terminal_summary(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-terminal-summary"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")

    rasp_events = build_rasp_events(
        run_id="run-terminal-summary",
        engine="codex",
        attempt_number=1,
        status="failed",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
    )
    fcmp_events = build_fcmp_events(
        rasp_events,
        status="failed",
        status_updated_at="2026-03-07T00:00:00Z",
        orchestrator_events=[
            {
                "ts": "2026-03-07T00:00:00Z",
                "attempt_number": 1,
                "seq": 2,
                "category": "lifecycle",
                "type": "lifecycle.run.terminal",
                "data": {
                    "status": "failed",
                    "code": "PROCESS_EXIT_NONZERO",
                    "message": "engine exited with non-zero status",
                },
            }
        ],
    )

    terminal_events = [
        event
        for event in fcmp_events
        if event.type == "conversation.state.changed" and event.data.get("to") == "failed"
    ]
    assert len(terminal_events) == 1
    terminal_payload = terminal_events[0].data["terminal"]
    assert terminal_payload["error"]["code"] == "PROCESS_EXIT_NONZERO"
    assert terminal_payload["error"]["message"] == "engine exited with non-zero status"


def test_translate_orchestrator_error_run_failed_maps_to_diagnostic_warning() -> None:
    specs = translate_orchestrator_event_to_fcmp_specs(
        engine="codex",
        type_name="error.run.failed",
        data={
            "message": "orchestrator failed to materialize attempt",
            "code": "ORCHESTRATOR_ERROR",
        },
        updated_at="2026-03-07T00:00:00Z",
        default_attempt_number=1,
    )
    assert len(specs) == 1
    assert specs[0]["type_name"] == "diagnostic.warning"
    assert specs[0]["data"]["code"] == "ORCHESTRATOR_ERROR"
    assert specs[0]["data"]["detail"] == "orchestrator failed to materialize attempt"


def test_fcmp_maps_auth_session_busy_to_diagnostic_warning(tmp_path: Path):
    run_dir = tmp_path / "run-auth-busy"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")

    rasp_events = build_rasp_events(
        run_id="run-auth-busy",
        engine="opencode",
        attempt_number=2,
        status="waiting_auth",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
    )
    fcmp_events = build_fcmp_events(
        rasp_events,
        status="waiting_auth",
        status_updated_at="2026-03-04T00:00:00",
        orchestrator_events=[
            {
                "ts": "2026-03-04T00:00:00",
                "attempt_number": 2,
                "seq": 1,
                "category": "interaction",
                "type": "auth.session.busy",
                "data": {
                    "engine": "opencode",
                    "provider_id": "google",
                    "last_error": "Auth session already active: auth-1",
                },
            }
        ],
    )

    diagnostic = next(
        event
        for event in fcmp_events
        if event.type == "diagnostic.warning" and event.data.get("code") == "AUTH_SESSION_BUSY"
    )
    assert diagnostic.data["code"] == "AUTH_SESSION_BUSY"
    assert not any(event.type == "auth.challenge.updated" for event in fcmp_events)


def test_fcmp_emits_only_current_attempt_reply_event(tmp_path: Path):
    run_dir = tmp_path / "run-state-reply"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    rasp_events = build_rasp_events(
        run_id="run-state-reply",
        engine="codex",
        attempt_number=3,
        status="running",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
    )
    interaction_history = [
        {
            "interaction_id": 2,
            "source_attempt": 2,
            "event_type": "reply",
            "payload": {
                "resolution_mode": "user_reply",
                "resolved_at": "2026-02-24T00:00:01",
                "response": {"text": "user answer"},
                "source_attempt": 2,
            },
            "created_at": "2026-02-24T00:00:01",
        },
        {
            "interaction_id": 1,
            "source_attempt": 1,
            "event_type": "reply",
            "payload": {
                "resolution_mode": "auto_decide_timeout",
                "resolved_at": "2026-02-24T00:00:02",
                "auto_decide_policy": "engine_judgement",
                "source_attempt": 1,
            },
            "created_at": "2026-02-24T00:00:02",
        },
    ]
    fcmp_events = build_fcmp_events(
        rasp_events,
        status="running",
        status_updated_at="2026-02-24T00:00:03",
        interaction_history=interaction_history,
        effective_session_timeout_sec=1200,
    )
    assert any(event.type == "interaction.reply.accepted" for event in fcmp_events)
    assert not any(event.type == "interaction.auto_decide.timeout" for event in fcmp_events)
    assert any(
        event.type == "conversation.state.changed"
        and event.data.get("trigger") == "interaction.reply.accepted"
        and event.data.get("to") == "queued"
        for event in fcmp_events
    )
    accepted = next(event for event in fcmp_events if event.type == "interaction.reply.accepted")
    assert accepted.data.get("response_preview") == "user answer"


def test_runtime_protocol_outputs_are_schema_valid(tmp_path: Path):
    run_dir = tmp_path / "run-schema-valid"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    pending = {"interaction_id": 5, "kind": "open_text", "prompt": "continue?"}

    rasp_events = build_rasp_events(
        run_id="run-schema-valid",
        engine="codex",
        attempt_number=1,
        status="waiting_user",
        pending_interaction=pending,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
    )
    fcmp_events = build_fcmp_events(
        rasp_events,
        status="waiting_user",
        status_updated_at="2026-02-24T00:00:00",
        pending_interaction=pending,
    )

    for event in rasp_events:
        validate_rasp_event(event.model_dump(mode="json"))
    for event in fcmp_events:
        validate_fcmp_event(event.model_dump(mode="json"))


def test_build_fcmp_events_raises_on_schema_violation(monkeypatch, tmp_path: Path):
    run_dir = tmp_path / "run-schema-invalid"
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "stdout.txt").write_text("", encoding="utf-8")
    (logs_dir / "stderr.txt").write_text("", encoding="utf-8")
    rasp_events = build_rasp_events(
        run_id="run-schema-invalid",
        engine="codex",
        attempt_number=1,
        status="running",
        pending_interaction=None,
        stdout_path=logs_dir / "stdout.txt",
        stderr_path=logs_dir / "stderr.txt",
    )

    monkeypatch.setattr(
        runtime_event_protocol,
        "make_fcmp_state_changed",
        lambda **_kwargs: {"to": "running"},
    )
    with pytest.raises(ProtocolSchemaViolation):
        build_fcmp_events(
            rasp_events,
            status="running",
            status_updated_at="2026-02-24T00:00:00",
        )
