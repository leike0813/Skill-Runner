import pytest

from server.runtime.protocol.schema_registry import (
    ProtocolSchemaViolation,
    validate_chat_replay_event,
    validate_chat_replay_history_response,
)


def test_validate_chat_replay_event_accepts_user_auth_submission() -> None:
    payload = {
        "protocol_version": "chat-replay/1.0",
        "seq": 3,
        "run_id": "run-chat-1",
        "attempt": 2,
        "role": "user",
        "kind": "auth_submission",
        "text": "API key submitted",
        "created_at": "2026-03-04T10:00:00Z",
        "correlation": {
            "auth_session_id": "auth-1",
            "submission_kind": "api_key",
            "fcmp_seq": 9,
        },
    }
    assert validate_chat_replay_event(payload) == payload


def test_validate_chat_replay_history_response_accepts_events() -> None:
    payload = {
        "events": [
            {
                "protocol_version": "chat-replay/1.0",
                "seq": 1,
                "run_id": "run-chat-2",
                "attempt": 1,
                "role": "assistant",
                "kind": "assistant_final",
                "text": "hello",
                "created_at": "2026-03-04T10:00:00Z",
                "correlation": {"fcmp_seq": 1},
            }
        ],
        "source": "live",
        "cursor_floor": 1,
        "cursor_ceiling": 1,
    }
    assert validate_chat_replay_history_response(payload) == payload


def test_validate_chat_replay_event_accepts_assistant_process() -> None:
    payload = {
        "protocol_version": "chat-replay/1.0",
        "seq": 9,
        "run_id": "run-chat-process",
        "attempt": 1,
        "role": "assistant",
        "kind": "assistant_process",
        "text": "Inspecting context",
        "created_at": "2026-03-04T10:00:00Z",
        "correlation": {
            "process_type": "reasoning",
            "message_id": "m-9",
            "fcmp_seq": 21,
        },
    }
    assert validate_chat_replay_event(payload) == payload


def test_validate_chat_replay_event_accepts_assistant_message() -> None:
    payload = {
        "protocol_version": "chat-replay/1.0",
        "seq": 10,
        "run_id": "run-chat-message",
        "attempt": 1,
        "role": "assistant",
        "kind": "assistant_message",
        "text": "Draft answer",
        "created_at": "2026-03-04T10:00:00Z",
        "correlation": {
            "message_id": "m-10",
            "fcmp_seq": 22,
        },
    }
    assert validate_chat_replay_event(payload) == payload


def test_validate_chat_replay_event_rejects_invalid_role() -> None:
    with pytest.raises(ProtocolSchemaViolation):
        validate_chat_replay_event(
            {
                "protocol_version": "chat-replay/1.0",
                "seq": 1,
                "run_id": "run-chat-bad",
                "attempt": 1,
                "role": "tool",
                "kind": "assistant_final",
                "text": "bad",
                "created_at": "2026-03-04T10:00:00Z",
                "correlation": {},
            }
        )
