from __future__ import annotations

from server.models.runtime_event import ConversationEventEnvelope, RuntimeEventEnvelope
from tests.common.protocol_golden_fixture_normalizer import (
    normalize_fcmp_event,
    normalize_outcome_result,
    normalize_rasp_event,
)


def test_protocol_golden_normalizer_removes_unstable_rasp_fields() -> None:
    event = RuntimeEventEnvelope.model_validate(
        {
            "run_id": "run-1",
            "seq": 42,
            "ts": "2026-04-16T12:00:00Z",
            "source": {"engine": "codex", "parser": "codex_ndjson", "confidence": 1.0},
            "event": {"category": "agent", "type": "agent.turn_failed"},
            "data": {"fatal": True},
            "correlation": {"request_id": "req-1", "session_id": "thread-1"},
            "attempt_number": 1,
            "raw_ref": {"attempt_number": 1, "stream": "stdout", "byte_from": 10, "byte_to": 20},
        }
    )
    normalized = normalize_rasp_event(event)
    assert "seq" not in normalized
    assert normalized["type"] == "agent.turn_failed"
    assert normalized["correlation"] == {"session_id": "thread-1"}
    assert normalized["raw_ref"] == {"attempt_number": 1, "stream": "stdout", "encoding": "utf-8"}


def test_protocol_golden_normalizer_removes_unstable_fcmp_fields() -> None:
    event = ConversationEventEnvelope.model_validate(
        {
            "run_id": "run-1",
            "seq": 99,
            "ts": "2026-04-16T12:00:00Z",
            "engine": "codex",
            "type": "diagnostic.warning",
            "data": {"code": "ENGINE_RATE_LIMIT_HINT"},
            "meta": {"local_seq": 3, "attempt": 1},
            "correlation": {"publish_id": "pub-1", "session_id": "thread-1"},
            "raw_ref": {"attempt_number": 1, "stream": "stdout", "byte_from": 5, "byte_to": 8}
        }
    )
    normalized = normalize_fcmp_event(event)
    assert normalized["type"] == "diagnostic.warning"
    assert normalized["meta"] == {"attempt": 1}
    assert normalized["correlation"] == {"session_id": "thread-1"}


def test_protocol_golden_normalizer_normalizes_outcome_mapping() -> None:
    normalized = normalize_outcome_result(
        {
            "final_status": "waiting_auth",
            "auth_session_meta": {"session_id": "auth-1", "provider_id": "openai"},
            "request_id": "req-1",
        },
        ignore_fields=["auth_session_meta.session_id"],
    )
    assert normalized == {
        "final_status": "waiting_auth",
        "auth_session_meta": {"provider_id": "openai"},
    }


def test_protocol_golden_normalizer_preserves_multi_attempt_semantics() -> None:
    normalized = normalize_outcome_result(
        {
            "attempts": [
                {"attempt_number": 1, "status_hint": "waiting_user", "request_id": "req-1"},
                {"attempt_number": 2, "status_hint": "succeeded", "request_id": "req-1"},
            ],
            "run_id": "run-1",
        }
    )
    assert normalized == {
        "attempts": [
            {"attempt_number": 1, "status_hint": "waiting_user"},
            {"attempt_number": 2, "status_hint": "succeeded"},
        ]
    }
