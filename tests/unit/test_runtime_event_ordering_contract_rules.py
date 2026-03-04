from tests.common.runtime_event_ordering_contract import load_runtime_event_ordering_contract


def test_runtime_event_ordering_contract_declares_auth_and_terminal_precedence() -> None:
    payload = load_runtime_event_ordering_contract()
    precedence = {row["id"]: row for row in payload["precedence_rules"]}
    assert precedence["PR-01"]["before"] == "auth.method.selection.required"
    assert precedence["PR-01"]["after"] == "auth.challenge.updated"
    assert precedence["PR-01"]["when"] == {"auth_route": "multi_method"}
    assert precedence["PR-04"] == {
        "id": "PR-04",
        "before": "assistant.message.final",
        "after": "conversation.state.changed.succeeded",
    }


def test_runtime_event_ordering_contract_declares_projection_gate() -> None:
    payload = load_runtime_event_ordering_contract()
    gating = {row["id"]: row for row in payload["gating_rules"]}
    assert gating["GR-02"]["event_kind"] == "conversation.state.changed.succeeded"
    assert gating["GR-02"]["requires"] == ["assistant.message.final"]
    assert gating["GR-01"]["when"] == {"auth_route": "multi_method"}
    assert gating["GR-01B"]["when"] == {"auth_route": "single_method"}
    assert gating["GR-01B"]["bypasses"] == ["auth.method.selection.required"]
    assert gating["GR-03"]["event_kind"] == "projection.terminal.result"
    assert gating["GR-03"]["requires_one_of"] == [
        "conversation.state.changed.succeeded",
        "conversation.state.changed.failed",
        "conversation.state.changed.canceled",
    ]


def test_runtime_event_ordering_contract_declares_single_method_busy_recovery() -> None:
    payload = load_runtime_event_ordering_contract()
    normalization = payload["lifecycle_normalization_rules"]
    assert normalization["auth_routes"]["single_method"]["requires_method_selection"] is False
    assert normalization["busy_recovery"]["single_method"] == {
        "preserve_phase": "challenge_active",
        "reproject_existing_challenge": True,
        "forbid_method_selection_demotion": True,
    }


def test_runtime_event_ordering_contract_declares_replay_rules() -> None:
    payload = load_runtime_event_ordering_contract()
    replay = payload["replay_rules"]
    assert replay["canonical_source"] == "publish_order"
    assert replay["live_delivery"] == "memory_first"
    assert replay["history_replay"] == "memory_first_audit_fallback"
    assert replay["audit_must_not_redefine_active_order"] is True
    assert replay["batch_backfill_must_not_override_live_order"] is True
