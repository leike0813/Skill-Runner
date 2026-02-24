from server.services import session_statechart
from tests.common.session_invariant_contract import (
    canonical_states,
    contract_path,
    fcmp_state_changed_tuples,
    initial_state,
    load_session_invariant_contract,
    ordering_rules,
    paired_event_rules,
    terminal_states,
    transition_tuples,
)


def test_invariant_contract_file_exists_and_loadable() -> None:
    assert contract_path().exists()
    payload = load_session_invariant_contract()
    assert payload["version"] == 1


def test_canonical_states_and_terminals_match_session_statechart() -> None:
    transitions = tuple(session_statechart.transition_rows())
    expected_states = {row.source for row in transitions} | {row.target for row in transitions}
    assert canonical_states() == expected_states
    assert terminal_states() == session_statechart.TERMINAL_STATES
    assert initial_state() == "queued"


def test_transition_set_is_exactly_equal_to_session_statechart() -> None:
    expected = {
        (row.source, row.event, row.target)
        for row in session_statechart.transition_rows()
    }
    assert transition_tuples() == expected


def test_fcmp_mapping_references_declared_state_space() -> None:
    states = canonical_states()
    for source, target, trigger in fcmp_state_changed_tuples():
        assert source in states
        assert target in states
        assert isinstance(trigger, str) and trigger


def test_paired_event_rules_point_to_state_changed_rows() -> None:
    state_changed = fcmp_state_changed_tuples()
    rules = paired_event_rules()
    assert rules
    for event_type, required_transition in rules.items():
        assert event_type
        assert required_transition in state_changed


def test_ordering_rules_are_complete_for_model_tests() -> None:
    assert ordering_rules() == {
        "terminal_state_unique",
        "waiting_user_requires_input_event",
        "seq_monotonic_contiguous",
        "reply_accepted_precedes_resumed_assistant",
    }
