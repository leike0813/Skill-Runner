from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import yaml  # type: ignore[import-untyped]


def _first_existing_path(candidates: Iterable[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _require_path(candidates: Iterable[Path], *, label: str) -> Path:
    matched = _first_existing_path(candidates)
    if matched is None:
        joined = ", ".join(str(path) for path in candidates)
        raise RuntimeError(f"{label} not found. tried: {joined}")
    return matched


def load_json_from_candidates(candidates: Iterable[Path], *, label: str) -> dict[str, Any]:
    path = _require_path(candidates, label=label)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} must be a JSON object: {path}")
    return payload


def load_yaml_from_candidates(candidates: Iterable[Path], *, label: str) -> dict[str, Any]:
    path = _require_path(candidates, label=label)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} must be a YAML mapping: {path}")
    return payload
