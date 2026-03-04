from server.models.runtime_event import FcmpEventType
from server.runtime.protocol.factories import make_fcmp_state_changed


def test_conversation_lifecycle_reduces_to_state_changed_only() -> None:
    event_types = {member.value for member in FcmpEventType}
    assert "conversation.state.changed" in event_types
    assert "conversation.started" not in event_types
    assert "conversation.completed" not in event_types
    assert "conversation.failed" not in event_types


def test_terminal_state_changed_carries_terminal_payload() -> None:
    payload = make_fcmp_state_changed(
        source_state="running",
        target_state="failed",
        trigger="turn.failed",
        updated_at="2026-03-04T00:00:00Z",
        pending_interaction_id=None,
        terminal={
            "status": "failed",
            "reason_code": "NON_ZERO_EXIT",
            "error": {"category": "runtime", "code": "NON_ZERO_EXIT", "message": "boom"},
            "diagnostics": ["X"],
        },
    )
    assert payload["terminal"]["status"] == "failed"
    assert payload["terminal"]["error"]["code"] == "NON_ZERO_EXIT"


def test_non_terminal_state_changed_omits_terminal_payload() -> None:
    payload = make_fcmp_state_changed(
        source_state="running",
        target_state="waiting_user",
        trigger="turn.needs_input",
        updated_at="2026-03-04T00:00:00Z",
        pending_interaction_id=None,
    )
    assert "terminal" not in payload
