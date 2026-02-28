from __future__ import annotations

from itertools import product
from typing import Dict, Iterable, Optional, Tuple

from server.runtime.session import statechart as session_statechart
from tests.common.session_invariant_contract import (
    canonical_states,
    initial_state,
    terminal_states,
    transition_index,
    transition_tuples,
)


def _walk(
    index: Dict[Tuple[str, str], str],
    start: str,
    events: Iterable[str],
) -> Tuple[str, bool]:
    state = start
    for event in events:
        key = (state, event)
        if key not in index:
            return state, False
        state = index[key]
    return state, True


def test_transition_keys_are_unique_and_match_contract() -> None:
    contract_index = transition_index()
    assert len(contract_index) == len(transition_tuples())


def test_all_declared_states_are_reachable_from_initial_state() -> None:
    adjacency: dict[str, set[str]] = {}
    for source, _, target in transition_tuples():
        adjacency.setdefault(source, set()).add(target)

    visited: set[str] = set()
    frontier = [initial_state()]
    while frontier:
        state = frontier.pop()
        if state in visited:
            continue
        visited.add(state)
        frontier.extend(adjacency.get(state, set()) - visited)
    assert canonical_states() <= visited


def test_terminal_states_have_no_outgoing_edges() -> None:
    terminals = terminal_states()
    outgoing = [row for row in transition_tuples() if row[0] in terminals]
    assert outgoing == []


def test_waiting_user_outgoing_events_are_explicitly_bounded() -> None:
    waiting_events = {event for source, event, _ in transition_tuples() if source == "waiting_user"}
    assert waiting_events == {
        "interaction.reply.accepted",
        "interaction.auto_decide.timeout",
        "run.canceled",
        "restart.preserve_waiting",
        "restart.reconcile_failed",
    }


def test_model_and_implementation_transition_indices_are_equivalent() -> None:
    contract = transition_index()
    impl = {
        (row.source, row.event): row.target
        for row in session_statechart.transition_rows()
    }
    assert contract == impl


def test_finite_event_sequence_enumeration_matches_implementation_model() -> None:
    contract_index = transition_index()
    impl_index = {
        (row.source, row.event): row.target
        for row in session_statechart.transition_rows()
    }
    event_alphabet = sorted({event for _, event, _ in transition_tuples()})
    start = initial_state()

    for length in range(0, 5):
        for events in product(event_alphabet, repeat=length):
            contract_state, contract_valid = _walk(contract_index, start, events)
            impl_state, impl_valid = _walk(impl_index, start, events)
            assert (contract_state, contract_valid) == (impl_state, impl_valid)


def test_recovery_event_helper_matches_model_edges() -> None:
    index = transition_index()
    preserve = session_statechart.waiting_recovery_event(
        has_pending_interaction=True,
        has_valid_handle=True,
    )
    reconcile = session_statechart.waiting_recovery_event(
        has_pending_interaction=False,
        has_valid_handle=True,
    )
    assert index[("waiting_user", preserve)] == "waiting_user"
    assert index[("waiting_user", reconcile)] == "failed"
