from __future__ import annotations

import json
from pathlib import Path

from tests.common.runtime_parser_capability_contract import (
    load_runtime_parser_capability_contract,
    parser_capability_contract_path,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _stream_parser_source(engine: str) -> str:
    path = PROJECT_ROOT / "server" / "engines" / engine / "adapter" / "stream_parser.py"
    return path.read_text(encoding="utf-8")


def _adapter_profile(engine: str) -> dict[str, object]:
    path = PROJECT_ROOT / "server" / "engines" / engine / "adapter" / "adapter_profile.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_turn_start_capability(source: str) -> bool:
    return any(token in source for token in ("turn_started", "turn_start_seen", '"marker": "start"'))


def test_runtime_parser_capability_contract_is_loadable() -> None:
    assert parser_capability_contract_path().exists()
    payload = load_runtime_parser_capability_contract()
    assert payload["version"] == 1


def test_runtime_parser_capability_contract_declares_all_current_engines() -> None:
    payload = load_runtime_parser_capability_contract()
    assert set(payload["engines"]) == {"codex", "claude", "gemini", "opencode", "qwen"}


def test_runtime_parser_capability_contract_matches_current_engine_sources() -> None:
    payload = load_runtime_parser_capability_contract()
    for engine, capability_obj in payload["engines"].items():
        source = _stream_parser_source(engine)
        profile = _adapter_profile(engine)
        capability = capability_obj
        assert _assert_turn_start_capability(source) is capability["semantic_turn_markers"]["start"]
        assert ("turn_completed" in source) is capability["semantic_turn_markers"]["complete"]
        assert ("turn_failed" in source) is capability["semantic_turn_markers"]["failed"]
        assert ("classify_engine_error_payload" in source) is capability["generic_error_governance"]
        assert ("process_events" in source) is capability["process_event_extraction"]
        assert ("structured_payloads" in source) is capability["structured_payload_extraction"]
        assert ("run_handle" in source) is capability["run_handle_extraction"]
        assert ('"confidence"' in source) is capability["parser_confidence_reporting"]
        has_auth_patterns = "parser_auth_patterns" in profile and bool(profile["parser_auth_patterns"])
        assert has_auth_patterns is capability["auth_signal_snapshot"]


def test_runtime_parser_capability_contract_declares_common_parser_fallback_taxonomy() -> None:
    payload = load_runtime_parser_capability_contract()
    common = payload["common"]
    unknown = common["unknown_engine_fallback"]
    assert unknown["parser"] == "unknown"
    assert unknown["confidence"] == 0.2
    assert unknown["diagnostics"] == ["UNKNOWN_ENGINE_PROFILE"]
    assert unknown["taxonomy"] == {
        "severity": "warning",
        "pattern_kind": "parser_unknown_engine",
        "source_type": "parser:fallback",
        "authoritative": False,
    }
    low_confidence = common["low_confidence_parse_threshold"]
    assert low_confidence["lt"] == 0.7
    assert low_confidence["taxonomy"] == {
        "severity": "warning",
        "pattern_kind": "parser_low_confidence",
        "source_type": "parser:confidence",
        "authoritative": False,
    }
