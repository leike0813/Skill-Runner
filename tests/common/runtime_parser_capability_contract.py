from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "server" / "contracts" / "invariants" / "runtime_parser_capabilities.yaml"


def _as_mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"Invalid parser capability contract field `{field}`")
    return value


@lru_cache(maxsize=1)
def load_runtime_parser_capability_contract() -> Dict[str, Any]:
    if not CONTRACT_PATH.exists():
        raise RuntimeError(f"Parser capability contract file not found: {CONTRACT_PATH}")
    payload_obj = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload_obj, dict):
        raise RuntimeError("Parser capability contract root must be a mapping")
    _as_mapping(payload_obj.get("common"), field="common")
    _as_mapping(payload_obj.get("engines"), field="engines")
    return payload_obj


def parser_capability_contract_path() -> Path:
    return CONTRACT_PATH
