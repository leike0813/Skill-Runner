from __future__ import annotations

from tests.common.protocol_golden_fixture_loader import (
    list_fixture_ids,
    load_auth_detection_sample_bridge,
    load_fixture,
    load_fixture_if_supported,
)


def test_protocol_golden_fixture_loader_lists_and_hydrates_blob_inputs() -> None:
    fixture_ids = list_fixture_ids()
    assert "codex_turn_failed_protocol_smoke" in fixture_ids
    fixture = load_fixture("codex_turn_failed_protocol_smoke")
    assert "stdout" in fixture["inputs"]
    assert "usage limit" in fixture["inputs"]["stdout"]


def test_protocol_golden_fixture_loader_returns_none_for_unsupported_engine() -> None:
    fixture = load_fixture_if_supported(
        "codex_turn_failed_protocol_smoke",
        target_engine="gemini",
    )
    assert fixture is None


def test_protocol_golden_fixture_loader_exposes_auth_detection_bridge_sample() -> None:
    sample = load_auth_detection_sample_bridge("codex", "openai_usage_limit_plus")
    assert "usage limit" in sample["stdout"].lower()
