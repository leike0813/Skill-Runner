from __future__ import annotations

from tests.common.protocol_golden_fixture_assertions import (
    assert_diagnostics_match,
    assert_event_subsequence,
    assert_event_types_absent,
    assert_outcome_semantics,
)


def test_protocol_golden_assertions_support_event_subsequence_and_absence() -> None:
    actual = [
        {"type": "agent.turn_start", "data": {}},
        {"type": "diagnostic.warning", "data": {"code": "LOW_CONFIDENCE_PARSE"}},
        {"type": "agent.turn_failed", "data": {"fatal": True}},
    ]
    assert_event_subsequence(
        actual,
        [
            {"type": "agent.turn_start"},
            {"type": "agent.turn_failed", "data": {"fatal": True}},
        ],
    )
    assert_event_types_absent(actual, ["agent.turn_complete"])


def test_protocol_golden_assertions_match_diagnostics_and_outcome_semantics() -> None:
    actual_events = [
        {
            "type": "diagnostic.warning",
            "data": {
                "code": "ENGINE_RATE_LIMIT_HINT",
                "pattern_kind": "engine_rate_limit_hint",
                "source_type": "type:error",
                "authoritative": False,
            },
        }
    ]
    assert_diagnostics_match(
        actual_events,
        [
            {
                "type": "diagnostic.warning",
                "data": {
                    "code": "ENGINE_RATE_LIMIT_HINT",
                    "pattern_kind": "engine_rate_limit_hint",
                },
            }
        ],
    )
    assert_outcome_semantics(
        {
            "final_status": "waiting_auth",
            "pending_auth": {"provider_id": "openai", "last_error": "usage limit"},
        },
        {
            "final_status": "waiting_auth",
            "pending_auth": {"provider_id": "openai"},
        },
    )
