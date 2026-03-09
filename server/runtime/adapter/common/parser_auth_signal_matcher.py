from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import jsonschema  # type: ignore[import-untyped]

from server.config import config
from server.runtime.adapter.types import RuntimeAuthSignal


def detect_auth_signal_from_patterns(
    *,
    engine: str,
    rules: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    evidence: Mapping[str, Any],
) -> RuntimeAuthSignal | None:
    engine_id = engine.strip().lower()
    ordered_engine_rules = _sort_rules(rules)
    for rule in ordered_engine_rules:
        if not _matches_rule(rule, evidence):
            continue
        signal = _build_signal(evidence=evidence, rule=rule, confidence="high")
        if signal is not None:
            return signal

    fallback_rules = _load_common_fallback_rules()
    ordered_fallback_rules = _sort_rules(fallback_rules)
    for rule in ordered_fallback_rules:
        if not _matches_rule(rule, {**dict(evidence), "engine": engine_id}):
            continue
        signal = _build_signal(evidence=evidence, rule=rule, confidence="low")
        if signal is not None:
            return signal
    return None


def is_high_confidence_auth_required(signal: RuntimeAuthSignal | None) -> bool:
    if not isinstance(signal, dict):
        return False
    return bool(signal.get("required")) and signal.get("confidence") == "high"


def _build_signal(
    *,
    evidence: Mapping[str, Any],
    rule: dict[str, Any],
    confidence: str,
) -> RuntimeAuthSignal | None:
    provider_id = _resolve_field_value(dict(evidence), "provider_id")
    if provider_id is None:
        provider_id = _resolve_field_value(dict(evidence), "extracted.provider_id")
    provider_id_value = provider_id if isinstance(provider_id, str) and provider_id else None
    matched_pattern_id = str(rule.get("id") or "").strip() or None
    if matched_pattern_id is None:
        return None
    reason_code = _normalize_reason_code(matched_pattern_id)
    signal: RuntimeAuthSignal = {
        "required": True,
        "confidence": confidence,  # type: ignore[typeddict-item]
        "subcategory": None,
        "provider_id": provider_id_value,
        "reason_code": reason_code,
        "matched_pattern_id": matched_pattern_id,
    }
    return signal


def _normalize_reason_code(value: str) -> str:
    upper = re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")
    if not upper:
        return "AUTH_SIGNAL_MATCHED"
    return upper


def _sort_rules(rules: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (
            rule
            for rule in rules
            if isinstance(rule, dict) and bool(rule.get("enabled", True))
        ),
        key=lambda item: int(item.get("priority", 0)),
        reverse=True,
    )


def _matches_rule(rule: dict[str, Any], evidence: Mapping[str, Any]) -> bool:
    match = rule.get("match", {})
    if not isinstance(match, dict):
        return False
    all_clauses = match.get("all", [])
    any_clauses = match.get("any", [])
    if isinstance(all_clauses, list) and all_clauses:
        if not all(_matches_clause(dict(clause), evidence) for clause in all_clauses if isinstance(clause, dict)):
            return False
    if isinstance(any_clauses, list) and any_clauses:
        if not any(_matches_clause(dict(clause), evidence) for clause in any_clauses if isinstance(clause, dict)):
            return False
    return bool((isinstance(all_clauses, list) and all_clauses) or (isinstance(any_clauses, list) and any_clauses))


def _matches_clause(clause: dict[str, Any], evidence: Mapping[str, Any]) -> bool:
    field = clause.get("field")
    if not isinstance(field, str) or not field:
        return False
    op = clause.get("op")
    expected = clause.get("value")
    actual = _resolve_field_value(dict(evidence), field)
    if op == "eq":
        return actual == expected
    if op == "in":
        return actual in expected if isinstance(expected, list) else False
    if op == "regex":
        if not isinstance(actual, str) or not isinstance(expected, str):
            return False
        return re.search(expected, actual, re.IGNORECASE | re.MULTILINE) is not None
    if op == "contains":
        if isinstance(actual, str) and isinstance(expected, str):
            return expected.lower() in actual.lower()
        if isinstance(actual, list):
            return expected in actual
        return False
    if op == "gte":
        if actual is None or expected is None:
            return False
        try:
            return float(actual) >= float(expected)
        except (TypeError, ValueError):
            return False
    return False


def _resolve_field_value(evidence: dict[str, Any], field: str) -> Any:
    current: Any = evidence
    for part in field.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


@lru_cache(maxsize=1)
def _load_common_fallback_rules() -> tuple[dict[str, Any], ...]:
    root = Path(config.SYSTEM.ROOT).resolve()
    rules_path = root / "server" / "engines" / "common" / "auth_detection" / "common_fallback_patterns.json"
    schema_path = root / "server" / "contracts" / "schemas" / "auth_fallback_patterns.schema.json"
    if not rules_path.exists():
        return ()
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=payload, schema=schema)
    raw_rules = payload.get("rules", [])
    if not isinstance(raw_rules, list):
        return ()
    return tuple(rule for rule in raw_rules if isinstance(rule, dict))
