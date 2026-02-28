import pytest

from server.runtime.protocol.schema_registry import (
    ProtocolSchemaViolation,
    validate_fcmp_event,
    validate_interaction_history_entry,
    validate_orchestrator_event,
    validate_pending_interaction,
    validate_rasp_event,
    validate_resume_command,
)


def test_validate_fcmp_event_accepts_state_changed_payload():
    payload = {
        "protocol_version": "fcmp/1.0",
        "run_id": "run-1",
        "seq": 1,
        "ts": "2026-02-24T00:00:00",
        "engine": "codex",
        "type": "conversation.state.changed",
        "data": {
            "from": "running",
            "to": "waiting_user",
            "trigger": "turn.needs_input",
            "updated_at": "2026-02-24T00:00:00",
            "pending_interaction_id": 7,
        },
        "meta": {"attempt": 1},
        "raw_ref": None,
    }
    assert validate_fcmp_event(payload) == payload


def test_validate_fcmp_event_accepts_local_seq_meta() -> None:
    payload = {
        "protocol_version": "fcmp/1.0",
        "run_id": "run-1",
        "seq": 4,
        "ts": "2026-02-24T00:00:04",
        "engine": "codex",
        "type": "assistant.message.final",
        "data": {
            "message_id": "m-1",
            "text": "hello",
        },
        "meta": {"attempt": 2, "local_seq": 1},
        "raw_ref": None,
    }
    assert validate_fcmp_event(payload) == payload


def test_validate_fcmp_event_rejects_missing_trigger():
    payload = {
        "protocol_version": "fcmp/1.0",
        "run_id": "run-1",
        "seq": 1,
        "ts": "2026-02-24T00:00:00",
        "engine": "codex",
        "type": "conversation.state.changed",
        "data": {
            "from": "running",
            "to": "waiting_user",
            "updated_at": "2026-02-24T00:00:00",
        },
        "meta": {"attempt": 1},
    }
    with pytest.raises(ProtocolSchemaViolation):
        validate_fcmp_event(payload)


def test_validate_pending_interaction_rejects_unknown_fields():
    with pytest.raises(ProtocolSchemaViolation):
        validate_pending_interaction(
            {
                "interaction_id": 1,
                "kind": "open_text",
                "prompt": "next",
                "unknown": True,
            }
        )


def test_validate_resume_command_rejects_extra_fields():
    with pytest.raises(ProtocolSchemaViolation):
        validate_resume_command(
            {
                "interaction_id": 1,
                "response": {"ok": True},
                "resolution_mode": "user_reply",
                "extra": "not-allowed",
            }
        )


def test_validate_orchestrator_event_accepts_diagnostic_warning():
    payload = {
        "ts": "2026-02-24T00:00:00",
        "attempt_number": 2,
        "seq": 1,
        "category": "diagnostic",
        "type": "diagnostic.warning",
        "data": {
            "code": "SCHEMA_INTERNAL_INVALID",
            "path": "pending_interaction",
            "detail": "missing prompt",
        },
    }
    assert validate_orchestrator_event(payload) == payload


def test_validate_rasp_event_accepts_terminal_payload():
    payload = {
        "protocol_version": "rasp/1.0",
        "run_id": "run-1",
        "seq": 3,
        "ts": "2026-02-24T00:00:00",
        "source": {
            "engine": "codex",
            "parser": "codex_parser",
            "confidence": 0.99,
        },
        "event": {
            "category": "lifecycle",
            "type": "lifecycle.run.terminal",
        },
        "data": {"status": "failed"},
        "correlation": {},
        "attempt_number": 1,
        "raw_ref": None,
    }
    assert validate_rasp_event(payload) == payload


def test_validate_interaction_history_entry_contract():
    payload = {
        "interaction_id": 7,
        "event_type": "reply",
        "payload": {
            "response": {"text": "ok"},
            "resolution_mode": "user_reply",
            "resolved_at": "2026-02-24T00:00:00",
        },
        "created_at": "2026-02-24T00:00:00",
    }
    assert validate_interaction_history_entry(payload) == payload
