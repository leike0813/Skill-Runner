from tests.common.agent_output_protocol_contract import (
    auto_final_contract,
    attempt_round_model,
    branch_by_name,
    contract_path,
    interactive_branch_names,
    legacy_deprecations,
    load_agent_output_protocol_contract,
    repair_audit_requirements,
    repair_event_requirements,
    repair_executor_ownership,
    repair_loop,
    repair_pipeline_order,
)


def test_agent_output_protocol_contract_exists_and_loads() -> None:
    assert contract_path().exists()
    payload = load_agent_output_protocol_contract()
    assert payload["version"] == 1


def test_auto_final_contract_declares_done_marker_as_compatibility_fallback() -> None:
    contract = auto_final_contract()
    assert contract["completion_protocol"] == "explicit_structured_output_or_done_signal_payload"
    assert contract["compatibility_fallback_marker"] == "__SKILL_DONE__"
    assert contract["compatibility_fallback_marker_value"] is True
    assert contract["output_type"] == "json_object"


def test_interactive_union_contract_has_exactly_final_and_pending_branches() -> None:
    assert interactive_branch_names() == ["final", "pending"]


def test_pending_branch_requires_false_done_marker_message_and_ui_hints() -> None:
    pending = branch_by_name("pending")
    assert pending["marker_value"] is False
    assert pending["required_fields"] == ["message", "ui_hints"]
    constraints = pending["field_constraints"]
    assert constraints["message"]["type"] == "string"
    assert constraints["message"]["min_length"] == 1
    assert constraints["ui_hints"]["type"] == "object"


def test_repair_loop_is_attempt_local_and_bounded() -> None:
    contract = repair_loop()
    assert contract["same_attempt"] is True
    assert contract["max_retries_default"] == 3
    assert contract["on_exhaustion"] == "fallback_after_exhaustion"
    assert contract["must_not_increment_attempt_number"] is True
    assert contract["must_not_directly_transition_to_waiting_user"] is True


def test_attempt_round_model_distinguishes_attempt_and_internal_round() -> None:
    contract = attempt_round_model()
    assert contract["attempt_role"] == "outer_lifecycle_execution_unit"
    assert contract["internal_round_role"] == "attempt_local_output_convergence_round"
    assert contract["internal_round_changes_attempt_number"] is False
    assert contract["default_internal_round_budget"] == 3


def test_repair_executor_ownership_assigns_single_orchestrator_owner() -> None:
    contract = repair_executor_ownership()
    assert contract["owner"] == "orchestrator_output_convergence_executor"
    assert contract["parser_role"] == "subordinate_candidate_preprocessor"
    assert contract["adapter_role"] == "subordinate_candidate_preprocessor"
    assert contract["interaction_service_role"] == "legacy_fallback_projection_only"


def test_repair_pipeline_order_unifies_repair_and_legacy_fallbacks() -> None:
    stages = repair_pipeline_order()["stages"]
    assert stages == [
        "deterministic_parse_repair",
        "schema_repair_rounds",
        "legacy_lifecycle_fallback",
        "legacy_result_file_fallback",
        "done_marker_fallback",
        "legacy_interactive_waiting_or_completion",
    ]


def test_repair_event_requirements_define_internal_diagnostic_event_surface() -> None:
    contract = repair_event_requirements()
    assert contract["category"] == "diagnostic"
    assert contract["allowed_types"] == [
        "diagnostic.output_repair.started",
        "diagnostic.output_repair.round.started",
        "diagnostic.output_repair.round.completed",
        "diagnostic.output_repair.converged",
        "diagnostic.output_repair.exhausted",
        "diagnostic.output_repair.skipped",
    ]
    assert contract["common_fields"] == [
        "attempt_number",
        "internal_round_index",
        "repair_stage",
        "candidate_source",
    ]
    per_type = contract["per_type_required_fields"]
    assert per_type["diagnostic.output_repair.exhausted"] == ["reason", "legacy_fallback_target"]
    assert per_type["diagnostic.output_repair.skipped"] == ["skip_reason", "legacy_fallback_target"]


def test_repair_audit_requirements_define_future_canonical_history_file() -> None:
    contract = repair_audit_requirements()
    assert contract["canonical_file"] == ".audit/output_repair.<attempt>.jsonl"
    assert contract["write_mode"] == "append_only"
    assert contract["authority"] == "history_only"
    assert "internal_round_index" in contract["required_fields"]
    assert "executor" in contract["required_fields"]


def test_legacy_deprecations_include_ask_user_yaml() -> None:
    contract = legacy_deprecations()
    assert "<ASK_USER_YAML>" in contract["deprecated_protocols"]
    assert contract["ask_user_schema_role"] == "ui_hints_capability_source"
