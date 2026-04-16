from __future__ import annotations

from tests.common.protocol_golden_fixture_assertions import (
    assert_diagnostics_match,
    assert_event_subsequence,
    assert_event_types_absent,
)
from tests.common.protocol_golden_fixture_harness import execute_protocol_core_fixture
from tests.common.protocol_golden_fixture_loader import load_fixture
from tests.common.protocol_golden_fixture_normalizer import (
    normalize_fcmp_event,
    normalize_rasp_event,
)


def test_runtime_event_protocol_golden_smoke(tmp_path) -> None:
    fixture = load_fixture("codex_turn_failed_protocol_smoke")
    rasp_events, fcmp_events = execute_protocol_core_fixture(fixture, tmp_path=tmp_path)
    ignore_fields = fixture["normalization"]["ignore_fields"]
    normalized_rasp = [
        normalize_rasp_event(event, ignore_fields=ignore_fields)
        for event in rasp_events
    ]
    normalized_fcmp = [
        normalize_fcmp_event(event, ignore_fields=ignore_fields)
        for event in fcmp_events
    ]

    assert_event_subsequence(normalized_rasp, fixture["expected"]["rasp_events"])
    assert_event_types_absent(normalized_rasp, fixture["expected"]["rasp_absent_event_types"])
    assert_event_subsequence(normalized_fcmp, fixture["expected"]["fcmp_events"])
    assert_diagnostics_match(normalized_rasp, fixture["expected"]["diagnostics"])
    assert_diagnostics_match(normalized_fcmp, fixture["expected"]["diagnostics"])
