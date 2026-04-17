from __future__ import annotations

import pytest

from tests.common.protocol_golden_fixture_assertions import assert_event_subsequence
from tests.common.protocol_golden_fixture_harness import execute_protocol_core_fixture
from tests.common.protocol_golden_fixture_loader import load_fixture
from tests.common.protocol_golden_fixture_normalizer import (
    normalize_fcmp_event,
    normalize_rasp_event,
)
from tests.engine_integration.golden_registry import captured_protocol_fixture_ids


@pytest.mark.parametrize("fixture_id", captured_protocol_fixture_ids(), ids=str)
def test_protocol_golden_engine_integration(fixture_id: str, tmp_path) -> None:
    fixture = load_fixture(fixture_id)
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

    assert fixture["expected"]["protocol"]["attempt_count"] == len(fixture["attempts"])
    assert_event_subsequence(normalized_rasp, fixture["expected"]["rasp_events"])
    assert_event_subsequence(normalized_fcmp, fixture["expected"]["fcmp_events"])
