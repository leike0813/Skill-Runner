from __future__ import annotations

from typing import Any


_TAXONOMY_BY_CODE: dict[str, dict[str, Any]] = {
    "UNKNOWN_ENGINE_PROFILE": {
        "severity": "warning",
        "pattern_kind": "parser_unknown_engine",
        "source_type": "parser:fallback",
        "authoritative": False,
    },
    "LOW_CONFIDENCE_PARSE": {
        "severity": "warning",
        "pattern_kind": "parser_low_confidence",
        "source_type": "parser:confidence",
        "authoritative": False,
    },
    "RAW_STDERR_COALESCED": {
        "severity": "warning",
        "pattern_kind": "protocol_raw_coalesced",
        "source_type": "protocol:raw_coalescer",
        "authoritative": False,
    },
    "RAW_DUPLICATE_SUPPRESSED": {
        "severity": "info",
        "pattern_kind": "protocol_raw_dedup",
        "source_type": "protocol:raw_dedup",
        "authoritative": False,
    },
    "TERMINAL_STATUS_COMPLETION_CONFLICT": {
        "severity": "warning",
        "pattern_kind": "protocol_completion_conflict",
        "source_type": "protocol:completion_state",
        "authoritative": False,
    },
    "INCOMPLETE_STATE_CLASSIFICATION": {
        "severity": "warning",
        "pattern_kind": "protocol_state_incomplete",
        "source_type": "protocol:state_classifier",
        "authoritative": False,
    },
    "RUN_HANDLE_CHANGED": {
        "severity": "warning",
        "pattern_kind": "protocol_run_handle_changed",
        "source_type": "protocol:run_handle",
        "authoritative": False,
    },
    "DELEGATED_PARSE": {
        "severity": "warning",
        "pattern_kind": "parser_delegated",
        "source_type": "parser:delegated",
        "authoritative": False,
    },
}


def classify_protocol_diagnostic_code(code: str) -> dict[str, Any]:
    normalized = code.strip()
    if not normalized:
        return {"authoritative": False}
    taxonomy = _TAXONOMY_BY_CODE.get(normalized)
    if taxonomy is not None:
        return dict(taxonomy)
    return {
        "severity": "warning",
        "pattern_kind": "protocol_diagnostic",
        "source_type": "protocol:generic",
        "authoritative": False,
    }
