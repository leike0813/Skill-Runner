from __future__ import annotations

import pytest

from tests.common.protocol_golden_fixture_assertions import assert_outcome_semantics
from tests.common.protocol_golden_fixture_harness import execute_outcome_core_fixture
from tests.common.protocol_golden_fixture_loader import load_fixture
from tests.common.protocol_golden_fixture_normalizer import normalize_outcome_result


@pytest.mark.asyncio
async def test_run_attempt_outcome_golden_smoke(tmp_path) -> None:
    fixture = load_fixture("common_outcome_waiting_auth_smoke")
    outcome = await execute_outcome_core_fixture(fixture, tmp_path=tmp_path)
    normalized = normalize_outcome_result(
        outcome,
        ignore_fields=fixture["normalization"]["ignore_fields"],
    )
    assert_outcome_semantics(normalized, fixture["expected"]["outcome"])
