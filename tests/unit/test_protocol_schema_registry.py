import pytest

from server.runtime.protocol.schema_registry import (
    ProtocolSchemaViolation,
    validate_current_run_projection,
    validate_fcmp_event,
    validate_interaction_history_entry,
    validate_orchestrator_event,
    validate_pending_interaction,
    validate_rasp_event,
    validate_resume_command,
    validate_terminal_run_result,
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
            "pending_owner": "waiting_user",
        },
        "meta": {"attempt": 1},
        "raw_ref": None,
    }
    assert validate_fcmp_event(payload) == payload


def test_validate_fcmp_event_accepts_terminal_state_changed_payload() -> None:
    payload = {
        "protocol_version": "fcmp/1.0",
        "run_id": "run-1",
        "seq": 2,
        "ts": "2026-03-04T00:00:02",
        "engine": "codex",
        "type": "conversation.state.changed",
        "data": {
            "from": "running",
            "to": "failed",
            "trigger": "turn.failed",
            "updated_at": "2026-03-04T00:00:02",
            "pending_interaction_id": None,
            "pending_auth_session_id": None,
            "terminal": {
                "status": "failed",
                "reason_code": "NON_ZERO_EXIT",
                "error": {
                    "category": "runtime",
                    "code": "NON_ZERO_EXIT",
                    "message": "boom",
                },
                "diagnostics": ["X"],
            },
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


def test_validate_fcmp_event_accepts_optional_correlation() -> None:
    payload = {
        "protocol_version": "fcmp/1.0",
        "run_id": "run-1",
        "seq": 9,
        "ts": "2026-03-04T00:00:09",
        "engine": "codex",
        "type": "assistant.message.final",
        "data": {
            "message_id": "m-9",
            "text": "hello",
        },
        "meta": {"attempt": 1, "local_seq": 2},
        "correlation": {"publish_id": "pub-9"},
        "raw_ref": None,
    }
    assert validate_fcmp_event(payload) == payload


def test_validate_fcmp_event_accepts_auth_required_method_selection() -> None:
    payload = {
        "protocol_version": "fcmp/1.0",
        "run_id": "run-1",
        "seq": 5,
        "ts": "2026-03-03T00:00:00",
        "engine": "codex",
        "type": "auth.required",
        "data": {
            "engine": "codex",
            "provider_id": None,
            "available_methods": ["callback", "device_auth"],
            "prompt": "Authentication is required. Choose how to continue.",
            "instructions": "Select an authentication method to continue.",
            "last_error": None,
            "source_attempt": 1,
            "phase": "method_selection",
            "ui_hints": {"widget": "choice"},
        },
        "meta": {"attempt": 1},
        "raw_ref": None,
    }
    assert validate_fcmp_event(payload) == payload


def test_validate_fcmp_event_accepts_callback_url_submission_kind() -> None:
    payload = {
        "protocol_version": "fcmp/1.0",
        "run_id": "run-1",
        "seq": 6,
        "ts": "2026-03-03T00:00:01",
        "engine": "gemini",
        "type": "auth.input.accepted",
        "data": {
            "auth_session_id": "auth-1",
            "submission_kind": "callback_url",
            "accepted_at": "2026-03-03T00:00:01Z",
        },
        "meta": {"attempt": 1},
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


def test_validate_orchestrator_event_accepts_auth_method_selection_required():
    payload = {
        "ts": "2026-03-03T00:00:00",
        "attempt_number": 1,
        "seq": 2,
        "category": "interaction",
        "type": "auth.method.selection.required",
        "data": {
            "engine": "codex",
            "provider_id": None,
            "available_methods": ["callback", "device_auth"],
            "prompt": "Authentication is required. Choose how to continue.",
            "instructions": "Select an authentication method to continue.",
            "last_error": None,
            "source_attempt": 1,
            "phase": "method_selection",
            "ui_hints": {"widget": "choice"},
        },
    }
    assert validate_orchestrator_event(payload) == payload


def test_validate_orchestrator_event_accepts_auth_method_selection_with_ask_user_hint():
    payload = {
        "ts": "2026-03-03T00:00:00",
        "attempt_number": 1,
        "seq": 3,
        "category": "interaction",
        "type": "auth.method.selection.required",
        "data": {
            "engine": "codex",
            "provider_id": None,
            "available_methods": ["callback", "device_auth"],
            "prompt": "Authentication is required. Choose how to continue.",
            "instructions": "Select an authentication method to continue.",
            "last_error": None,
            "source_attempt": 1,
            "phase": "method_selection",
            "ui_hints": {"widget": "choice", "hint": "Choose an authentication method."},
            "ask_user": {
                "kind": "choose_one",
                "prompt": "Authentication is required. Choose how to continue.",
                "hint": "Choose an authentication method.",
                "options": [
                    {"label": "Callback URL", "value": "callback"},
                    {"label": "Device Authorization", "value": "device_auth"},
                ],
            },
        },
    }
    assert validate_orchestrator_event(payload) == payload


def test_validate_orchestrator_event_accepts_interaction_reply_accepted() -> None:
    payload = {
        "ts": "2026-03-04T00:00:00Z",
        "attempt_number": 2,
        "seq": 4,
        "category": "interaction",
        "type": "interaction.reply.accepted",
        "data": {
            "interaction_id": 7,
            "resolution_mode": "user_reply",
            "accepted_at": "2026-03-04T00:00:05Z",
            "response_preview": "男，38，程序员",
        },
    }
    assert validate_orchestrator_event(payload) == payload


@pytest.mark.parametrize(
    ("type_name", "data"),
    [
        (
            "auth.session.created",
            {
                "auth_session_id": "auth-1",
                "engine": "opencode",
                "provider_id": "google",
                "auth_method": "callback",
                "challenge_kind": "callback_url",
                "prompt": "Paste callback URL",
                "auth_url": "https://auth.example.dev",
                "user_code": None,
                "instructions": "Paste callback URL here.",
                "accepts_chat_input": True,
                "input_kind": "callback_url",
                "last_error": None,
                "source_attempt": 1,
                "phase": "challenge_active",
                "timeout_sec": 900,
                "created_at": "2026-03-04T00:00:00Z",
                "expires_at": "2026-03-04T00:15:00Z",
            },
        ),
        (
            "auth.method.selected",
            {
                "auth_session_id": "auth-1",
                "engine": "opencode",
                "provider_id": "google",
                "auth_method": "callback",
                "challenge_kind": "callback_url",
                "prompt": "Paste callback URL",
                "auth_url": "https://auth.example.dev",
                "user_code": None,
                "instructions": "Paste callback URL here.",
                "accepts_chat_input": True,
                "input_kind": "callback_url",
                "last_error": None,
                "source_attempt": 1,
                "phase": "challenge_active",
                "timeout_sec": 900,
                "created_at": "2026-03-04T00:00:00Z",
                "expires_at": "2026-03-04T00:15:00Z",
            },
        ),
        (
            "auth.session.busy",
            {
                "engine": "opencode",
                "provider_id": "google",
                "available_methods": ["callback"],
                "prompt": "Authentication is required for provider 'google'. Choose how to continue.",
                "instructions": "Select an authentication method to continue. Previous error: busy",
                "last_error": "busy",
                "source_attempt": 1,
                "phase": "method_selection",
                "ui_hints": {"widget": "choice"},
            },
        ),
        (
            "auth.input.accepted",
            {
                "auth_session_id": "auth-1",
                "submission_kind": "callback_url",
                "accepted_at": "2026-03-04T00:00:10Z",
            },
        ),
        (
            "auth.session.completed",
            {
                "auth_session_id": "auth-1",
                "resume_attempt": 2,
                "source_attempt": 1,
                "target_attempt": 2,
                "resume_ticket_id": "ticket-1",
                "ticket_consumed": True,
                "completed_at": "2026-03-04T00:00:20Z",
            },
        ),
        (
            "auth.session.failed",
            {
                "auth_session_id": "auth-1",
                "message": "authorization failed",
                "code": "AUTH_FAILED",
                "failed_at": "2026-03-04T00:00:30Z",
            },
        ),
        (
            "auth.session.timed_out",
            {
                "auth_session_id": "auth-1",
                "engine": "opencode",
                "provider_id": "google",
                "auth_method": "callback",
                "challenge_kind": "callback_url",
                "prompt": "Authentication timed out.",
                "auth_url": None,
                "user_code": None,
                "instructions": "auth session expired before completion",
                "accepts_chat_input": True,
                "input_kind": "callback_url",
                "last_error": "auth session expired before completion",
                "source_attempt": 1,
                "phase": "challenge_active",
            },
        ),
    ],
)
def test_validate_orchestrator_event_accepts_auth_lifecycle_payloads(
    type_name: str,
    data: dict[str, object],
) -> None:
    payload = {
        "ts": "2026-03-04T00:00:00Z",
        "attempt_number": 1,
        "seq": 3,
        "category": "interaction",
        "type": type_name,
        "data": data,
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
        "source_attempt": 2,
        "event_type": "reply",
        "payload": {
            "response": {"text": "ok"},
            "resolution_mode": "user_reply",
            "resolved_at": "2026-02-24T00:00:00",
            "source_attempt": 2,
        },
        "created_at": "2026-02-24T00:00:00",
    }
    assert validate_interaction_history_entry(payload) == payload


def test_validate_fcmp_event_accepts_resume_ownership_fields():
    payload = {
        "protocol_version": "fcmp/1.0",
        "run_id": "run-1",
        "seq": 8,
        "ts": "2026-03-03T00:00:08",
        "engine": "codex",
        "type": "auth.completed",
        "data": {
            "auth_session_id": "auth-1",
            "completed_at": "2026-03-03T00:00:08Z",
            "resume_attempt": 2,
            "source_attempt": 1,
            "target_attempt": 2,
            "resume_ticket_id": "ticket-1",
            "ticket_consumed": True,
        },
        "meta": {"attempt": 1},
        "raw_ref": None,
    }
    assert validate_fcmp_event(payload) == payload


def test_validate_current_run_projection_accepts_waiting_user_payload() -> None:
    payload = {
        "request_id": "req-1",
        "run_id": "run-1",
        "status": "waiting_user",
        "updated_at": "2026-03-03T00:00:08Z",
        "current_attempt": 2,
        "pending_owner": "waiting_user",
        "pending_interaction_id": 7,
        "pending_auth_session_id": None,
        "resume_ticket_id": None,
        "resume_cause": None,
        "source_attempt": None,
        "target_attempt": None,
        "conversation_mode": "session",
        "requested_execution_mode": "interactive",
        "effective_execution_mode": "interactive",
        "effective_interactive_require_user_reply": True,
        "effective_interactive_reply_timeout_sec": 1200,
        "effective_session_timeout_sec": 1200,
        "error": None,
        "warnings": [],
    }
    assert validate_current_run_projection(payload) == payload


def test_validate_terminal_run_result_rejects_non_terminal_status() -> None:
    with pytest.raises(ProtocolSchemaViolation):
        validate_terminal_run_result(
            {
                "status": "waiting_user",
                "data": None,
                "artifacts": [],
                "repair_level": "none",
                "validation_warnings": [],
                "error": None,
            }
        )
