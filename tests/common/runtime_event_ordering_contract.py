from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "docs" / "contracts" / "runtime_event_ordering_contract.yaml"


def _as_mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"Invalid ordering contract field `{field}`")
    return value


def _as_list(value: Any, *, field: str) -> List[Any]:
    if not isinstance(value, list):
        raise RuntimeError(f"Invalid ordering contract field `{field}`")
    return value


@lru_cache(maxsize=1)
def load_runtime_event_ordering_contract() -> Dict[str, Any]:
    if not CONTRACT_PATH.exists():
        raise RuntimeError(f"Ordering contract file not found: {CONTRACT_PATH}")
    payload_obj = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload_obj, dict):
        raise RuntimeError("Ordering contract root must be a mapping")
    _as_list(payload_obj.get("streams"), field="streams")
    _as_mapping(payload_obj.get("ordering_domains"), field="ordering_domains")
    _as_list(payload_obj.get("event_kinds"), field="event_kinds")
    _as_list(payload_obj.get("precedence_rules"), field="precedence_rules")
    _as_list(payload_obj.get("gating_rules"), field="gating_rules")
    _as_list(payload_obj.get("projection_rules"), field="projection_rules")
    _as_mapping(payload_obj.get("replay_rules"), field="replay_rules")
    _as_mapping(payload_obj.get("buffer_policies"), field="buffer_policies")
    _as_mapping(payload_obj.get("lifecycle_normalization_rules"), field="lifecycle_normalization_rules")
    return payload_obj


def ordering_contract_path() -> Path:
    return CONTRACT_PATH
