from tests.common.runtime_event_ordering_contract import (
    load_runtime_event_ordering_contract,
    ordering_contract_path,
)


def test_runtime_event_ordering_contract_exists_and_loads() -> None:
    assert ordering_contract_path().exists()
    payload = load_runtime_event_ordering_contract()
    assert payload["version"] == 1


def test_runtime_event_ordering_contract_declares_lifecycle_normalization() -> None:
    payload = load_runtime_event_ordering_contract()
    rules = payload["lifecycle_normalization_rules"]
    assert rules["normalize_to"] == "conversation.state.changed"
    assert set(rules["remove"]) == {
        "conversation.started",
        "conversation.completed",
        "conversation.failed",
    }
    assert "conversation.state.changed" in payload["event_kinds"]
    assert "conversation.completed" not in payload["event_kinds"]
    assert "conversation.failed" not in payload["event_kinds"]


def test_runtime_event_ordering_contract_declares_buffer_policies() -> None:
    payload = load_runtime_event_ordering_contract()
    policies = payload["buffer_policies"]
    assert policies["fcmp"]["candidate_required"] is True
    assert policies["rasp"]["candidate_required"] is True
    assert policies["fcmp"]["direct_publish_forbidden"] is True
    assert policies["rasp"]["direct_publish_forbidden"] is True
