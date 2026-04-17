from __future__ import annotations

from pathlib import Path

import pytest

from tests.common.protocol_golden_fixture_extractor import (
    build_protocol_golden_fixture_from_source_run,
    list_protocol_golden_source_runs,
)


def test_protocol_golden_source_run_registry_lists_all_captured_runs() -> None:
    runs = list_protocol_golden_source_runs()
    assert len(runs) == 18
    keys = {item["source_run_key"] for item in runs}
    assert "demo_auto_skill__codex" in keys
    assert "literature_explainer__opencode" in keys


def test_protocol_golden_extractor_builds_single_attempt_protocol_fixture() -> None:
    fixture = build_protocol_golden_fixture_from_source_run(
        "demo_auto_skill__codex__protocol",
        source_run_key="demo_auto_skill__codex",
        layer="protocol_core",
    )
    assert fixture["source"] == "captured_run"
    assert fixture["capture_mode"] == "single_attempt"
    assert len(fixture["attempts"]) == 1
    assert fixture["expected"]["protocol"]["attempt_count"] == 1


def test_protocol_golden_extractor_builds_whole_run_outcome_fixture() -> None:
    fixture = build_protocol_golden_fixture_from_source_run(
        "demo_interactive_skill__qwen__outcome",
        source_run_key="demo_interactive_skill__qwen",
        layer="outcome_core",
    )
    assert fixture["capture_mode"] == "whole_run"
    assert len(fixture["attempts"]) == 3
    assert fixture["expected"]["outcome"]["final_status"] == "succeeded"


def test_protocol_golden_extractor_raises_for_missing_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.common import protocol_golden_fixture_extractor as extractor

    monkeypatch.setattr(extractor, "DATA_RUNS_ROOT", Path("/tmp/definitely-missing-runs-root"))
    with pytest.raises(RuntimeError, match="Captured run not found"):
        build_protocol_golden_fixture_from_source_run(
            "demo_auto_skill__claude__protocol",
            source_run_key="demo_auto_skill__claude",
            layer="protocol_core",
        )
