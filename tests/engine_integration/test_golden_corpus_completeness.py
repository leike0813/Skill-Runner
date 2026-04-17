from __future__ import annotations

from tests.engine_integration.golden_registry import (
    captured_outcome_fixture_ids,
    captured_protocol_fixture_ids,
    captured_source_run_keys,
)


def test_engine_integration_golden_corpus_covers_all_source_runs() -> None:
    protocol_ids = set(captured_protocol_fixture_ids())
    outcome_ids = set(captured_outcome_fixture_ids())
    source_run_keys = set(captured_source_run_keys())

    for source_run_key in source_run_keys:
        assert f"{source_run_key}__protocol" in protocol_ids
        assert f"{source_run_key}__outcome" in outcome_ids
