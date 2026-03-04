from __future__ import annotations

from pathlib import Path
from typing import Any

import json

import yaml  # type: ignore[import-untyped]
from jsonschema import ValidationError, validate  # type: ignore[import-untyped]

from .types import AuthDetectionRulePack


class RulePackLoadError(RuntimeError):
    pass


def load_rule_pack_schema(schema_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RulePackLoadError(f"Failed to load auth detection schema: {schema_path}") from exc
    if not isinstance(payload, dict):
        raise RulePackLoadError(f"Auth detection schema must be a JSON object: {schema_path}")
    return payload


def load_rule_pack(pack_path: Path, *, schema: dict[str, Any]) -> AuthDetectionRulePack:
    try:
        payload = yaml.safe_load(pack_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RulePackLoadError(f"Failed to load auth detection rule pack: {pack_path}") from exc
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise RulePackLoadError(f"Auth detection rule pack must be a mapping: {pack_path}")
    try:
        validate(payload, schema)
    except ValidationError as exc:
        raise RulePackLoadError(f"Invalid auth detection rule pack: {pack_path}: {exc.message}") from exc
    return payload  # type: ignore[return-value]
