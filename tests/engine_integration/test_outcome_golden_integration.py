from __future__ import annotations

import pytest

from tests.common.protocol_golden_fixture_assertions import assert_outcome_semantics
from tests.common.protocol_golden_fixture_harness import execute_outcome_core_fixture
from tests.common.protocol_golden_fixture_loader import load_fixture
from tests.common.protocol_golden_fixture_normalizer import normalize_outcome_result
from tests.engine_integration.golden_registry import captured_outcome_fixture_ids


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture_id", captured_outcome_fixture_ids(), ids=str)
async def test_outcome_golden_engine_integration(fixture_id: str, tmp_path) -> None:
    fixture = load_fixture(fixture_id)
    outcome = await execute_outcome_core_fixture(fixture, tmp_path=tmp_path)
    normalized = normalize_outcome_result(
        outcome,
        ignore_fields=fixture["normalization"]["ignore_fields"],
    )
    assert_outcome_semantics(normalized, fixture["expected"]["outcome"])
