from server.models import RunStatus
from server.runtime.session import statechart as session_statechart
from tests.common.session_invariant_contract import canonical_states, terminal_states


def test_transition_keys_are_unique() -> None:
    index = session_statechart.build_transition_index()
    assert len(index) == len(tuple(session_statechart.transition_rows()))


def test_state_reachability_from_queued() -> None:
    transitions = tuple(session_statechart.transition_rows())
    adjacency: dict[str, set[str]] = {}
    for row in transitions:
        adjacency.setdefault(row.source, set()).add(row.target)

    visited: set[str] = set()
    frontier = ["queued"]
    while frontier:
        state = frontier.pop()
        if state in visited:
            continue
        visited.add(state)
        frontier.extend(adjacency.get(state, set()) - visited)

    assert canonical_states() <= visited


def test_terminal_states_are_mutually_exclusive_and_have_no_outgoing_edges() -> None:
    transitions = tuple(session_statechart.transition_rows())
    terminals = terminal_states()

    for status in RunStatus:
        expected = status.value in terminals
        assert session_statechart.assert_terminal_status_exclusive(status) is expected

    outgoing_from_terminal = [row for row in transitions if row.source in terminals]
    assert outgoing_from_terminal == []


def test_waiting_recovery_event_contract() -> None:
    assert (
        session_statechart.waiting_recovery_event(
            has_pending_interaction=True,
            has_valid_handle=True,
        )
        == session_statechart.SessionEvent.RESTART_PRESERVE_WAITING
    )
    assert (
        session_statechart.waiting_recovery_event(
            has_pending_interaction=True,
            has_valid_handle=False,
        )
        == session_statechart.SessionEvent.RESTART_RECONCILE_FAILED
    )
    assert (
        session_statechart.waiting_recovery_event(
            has_pending_interaction=False,
            has_valid_handle=True,
        )
        == session_statechart.SessionEvent.RESTART_RECONCILE_FAILED
    )
