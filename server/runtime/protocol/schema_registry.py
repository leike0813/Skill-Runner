from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List

import jsonschema  # type: ignore[import-untyped]


SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "schemas"
    / "protocol"
    / "runtime_contract.schema.json"
)


class ProtocolSchemaViolation(ValueError):
    """Raised when runtime protocol payload does not satisfy schema contract."""

    def __init__(self, *, schema_name: str, detail: str, errors: List[Dict[str, str]]) -> None:
        super().__init__(f"{schema_name}: {detail}")
        self.schema_name = schema_name
        self.detail = detail
        self.errors = errors


def _normalize_path(path_items: Iterable[Any]) -> str:
    parts = [str(item) for item in path_items]
    if not parts:
        return "$"
    return "$." + ".".join(parts)


@lru_cache(maxsize=1)
def _schema_document() -> Dict[str, Any]:
    if not SCHEMA_PATH.exists():
        raise RuntimeError(f"Protocol schema file not found: {SCHEMA_PATH}")
    payload = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Protocol schema must be a JSON object: {SCHEMA_PATH}")
    return payload


@lru_cache(maxsize=32)
def _validator_for(def_name: str) -> jsonschema.Draft202012Validator:
    document = _schema_document()
    schema = {
        "$schema": document.get("$schema", "https://json-schema.org/draft/2020-12/schema"),
        "$ref": f"#/$defs/{def_name}",
        "$defs": document.get("$defs", {}),
    }
    return jsonschema.Draft202012Validator(schema)


def _validate_payload(payload: Dict[str, Any], *, def_name: str, schema_name: str) -> Dict[str, Any]:
    validator = _validator_for(def_name)
    issues = sorted(validator.iter_errors(payload), key=lambda err: (list(err.path), err.message))
    if not issues:
        return payload
    details: List[Dict[str, str]] = []
    for issue in issues:
        details.append(
            {
                "path": _normalize_path(issue.path),
                "message": issue.message,
            }
        )
    first = details[0]
    raise ProtocolSchemaViolation(
        schema_name=schema_name,
        detail=f"{first['path']}: {first['message']}",
        errors=details,
    )


def validate_fcmp_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _validate_payload(payload, def_name="fcmp_event_envelope", schema_name="fcmp_event_envelope")


def validate_chat_replay_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _validate_payload(
        payload,
        def_name="chat_replay_event_envelope",
        schema_name="chat_replay_event_envelope",
    )


def validate_chat_replay_history_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _validate_payload(
        payload,
        def_name="chat_replay_history_response",
        schema_name="chat_replay_history_response",
    )


def validate_rasp_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _validate_payload(payload, def_name="rasp_event_envelope", schema_name="rasp_event_envelope")


def validate_orchestrator_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _validate_payload(payload, def_name="orchestrator_event", schema_name="orchestrator_event")


def validate_pending_interaction(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _validate_payload(payload, def_name="pending_interaction", schema_name="pending_interaction")


def validate_pending_auth(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _validate_payload(payload, def_name="pending_auth", schema_name="pending_auth")


def validate_pending_auth_method_selection(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _validate_payload(
        payload,
        def_name="pending_auth_method_selection",
        schema_name="pending_auth_method_selection",
    )


def validate_interaction_history_entry(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _validate_payload(
        payload,
        def_name="interaction_history_entry",
        schema_name="interaction_history_entry",
    )


def validate_resume_command(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _validate_payload(
        payload,
        def_name="interactive_resume_command",
        schema_name="interactive_resume_command",
    )


def validate_current_run_projection(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _validate_payload(
        payload,
        def_name="current_run_projection",
        schema_name="current_run_projection",
    )


def validate_terminal_run_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _validate_payload(
        payload,
        def_name="terminal_run_result",
        schema_name="terminal_run_result",
    )


def validate_run_state_envelope(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _validate_payload(
        payload,
        def_name="run_state_envelope",
        schema_name="run_state_envelope",
    )


def validate_run_dispatch_envelope(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _validate_payload(
        payload,
        def_name="run_dispatch_envelope",
        schema_name="run_dispatch_envelope",
    )
