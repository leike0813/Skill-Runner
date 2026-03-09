from server.runtime.session import statechart as session_statechart
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
        "waiting_auth_requires_auth_event",
        "seq_monotonic_contiguous",
        "reply_accepted_precedes_resumed_assistant",
        "auth_completed_single_consumer",
        "resume_ticket_single_start",
        "attempt_boundary_monotonic",
        "pending_owner_unique",
        "pending_history_attempt_consistent",
        "interaction_identity_unique_per_attempt",
        "terminal_result_matches_status",
        "recovery_resume_winner_unique",
        "current_projection_single_source_of_truth",
        "non_terminal_status_must_not_have_terminal_result",
        "terminal_result_requires_terminal_status",
        "current_pending_owner_matches_status",
        "leaving_waiting_clears_previous_pending_owner",
        "current_projection_and_resume_ticket_consistent",
        "fcmp_current_state_must_match_projection",
        "waiting_auth_requires_session_capability",
        "waiting_user_requires_interactive_session_capability",
        "non_session_auth_failfast_boundary",
        "non_session_interactive_zero_timeout_autoreply",
        "queued_requires_state_file",
        "queued_redrive_requires_run_dir",
        "orphan_queued_run_reconciles_terminal",
        "runtime_slot_release_on_nonstarted_exit",
        "dispatch_phase_monotonic",
        "worker_claim_precedes_attempt_start",
        "attempt_audit_skeleton_precedes_turn_started",
        "terminal_result_terminal_only",
        "audit_files_are_history_only",
        "parser_diagnostics_non_authoritative",
        "state_and_dispatch_consistent",
        "pending_owner_embedded_in_state",
        "state_file_single_source_of_truth",
        "fcmp_live_publish_precedes_audit_mirror",
        "rasp_live_publish_precedes_audit_mirror",
        "sse_delivery_must_not_depend_on_fcmp_file_materialization",
        "history_memory_first_audit_fallback",
        "fcmp_seq_assigned_at_publish_time",
        "rasp_seq_assigned_at_publish_time",
        "fcmp_rasp_publish_order_must_be_stable_per_emission",
        "publish_order_is_canonical_for_active_runtime_events",
        "audit_mirror_must_not_redefine_active_event_order",
        "rasp_order_defined_by_live_parser_emission_order",
        "fcmp_order_defined_by_shared_publisher_sequence",
        "auth_selection_must_precede_dependent_challenge_publication",
        "auth_completion_requires_terminal_session_state",
        "auth_ready_must_not_drive_resume",
        "waiting_state_must_not_emit_terminal_result_projection",
        "waiting_auth_exit_requires_auth_completed",
        "resume_ticket_auth_completed_requires_canonical_completion",
        "history_replay_must_preserve_canonical_publish_order",
        "batch_backfill_must_not_override_live_order",
        "conversation_lifecycle_normalized_to_state_changed_only",
        "single_method_auth_challenge_bypasses_selection",
        "single_method_auth_busy_reprojects_existing_challenge",
        "single_method_busy_reprojects_challenge_without_resume",
        "terminal_failed_should_include_error_summary_when_available",
        "auth_signal_sources_single_source",
        "lifecycle_consumes_auth_signal_snapshot_only",
        "low_confidence_auth_signal_must_not_enter_waiting_auth",
        "rasp_auth_signal_diagnostic_payload_structured",
    }
