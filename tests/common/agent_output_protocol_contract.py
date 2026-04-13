from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "server" / "contracts" / "invariants" / "agent_output_protocol_invariants.yaml"


def _as_mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"Invalid output protocol contract field `{field}`")
    return value


def _as_list(value: Any, *, field: str) -> List[Any]:
    if not isinstance(value, list):
        raise RuntimeError(f"Invalid output protocol contract field `{field}`")
    return value


def _as_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Invalid output protocol contract field `{field}`")
    return value.strip()


@lru_cache(maxsize=1)
def load_agent_output_protocol_contract() -> Dict[str, Any]:
    if not CONTRACT_PATH.exists():
        raise RuntimeError(f"Output protocol contract file not found: {CONTRACT_PATH}")
    payload_obj = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload_obj, dict):
        raise RuntimeError("Output protocol contract root must be a mapping")

    _as_mapping(payload_obj.get("auto_final_contract"), field="auto_final_contract")
    _as_mapping(payload_obj.get("interactive_union_contract"), field="interactive_union_contract")
    _as_mapping(payload_obj.get("repair_loop"), field="repair_loop")
    _as_mapping(payload_obj.get("attempt_round_model"), field="attempt_round_model")
    _as_mapping(payload_obj.get("repair_executor_ownership"), field="repair_executor_ownership")
    _as_mapping(payload_obj.get("repair_pipeline_order"), field="repair_pipeline_order")
    _as_mapping(payload_obj.get("repair_event_requirements"), field="repair_event_requirements")
    _as_mapping(payload_obj.get("audit_requirements"), field="audit_requirements")
    _as_mapping(payload_obj.get("repair_audit_requirements"), field="repair_audit_requirements")
    _as_mapping(payload_obj.get("legacy_deprecations"), field="legacy_deprecations")
    return payload_obj


def contract_path() -> Path:
    return CONTRACT_PATH


def auto_final_contract() -> Mapping[str, Any]:
    return _as_mapping(load_agent_output_protocol_contract()["auto_final_contract"], field="auto_final_contract")


def interactive_union_contract() -> Mapping[str, Any]:
    return _as_mapping(
        load_agent_output_protocol_contract()["interactive_union_contract"],
        field="interactive_union_contract",
    )


def interactive_branch_names() -> List[str]:
    contract = interactive_union_contract()
    branches = _as_list(contract.get("branches"), field="interactive_union_contract.branches")
    return [
        _as_str(_as_mapping(branch, field="interactive_union_contract.branches[]").get("name"), field="interactive_union_contract.branches[].name")
        for branch in branches
    ]


def branch_by_name(name: str) -> Mapping[str, Any]:
    contract = interactive_union_contract()
    branches = _as_list(contract.get("branches"), field="interactive_union_contract.branches")
    for branch in branches:
        mapping = _as_mapping(branch, field="interactive_union_contract.branches[]")
        if _as_str(mapping.get("name"), field="interactive_union_contract.branches[].name") == name:
            return mapping
    raise KeyError(name)


def repair_loop() -> Mapping[str, Any]:
    return _as_mapping(load_agent_output_protocol_contract()["repair_loop"], field="repair_loop")


def attempt_round_model() -> Mapping[str, Any]:
    return _as_mapping(load_agent_output_protocol_contract()["attempt_round_model"], field="attempt_round_model")


def repair_executor_ownership() -> Mapping[str, Any]:
    return _as_mapping(
        load_agent_output_protocol_contract()["repair_executor_ownership"],
        field="repair_executor_ownership",
    )


def repair_pipeline_order() -> Mapping[str, Any]:
    return _as_mapping(load_agent_output_protocol_contract()["repair_pipeline_order"], field="repair_pipeline_order")


def repair_event_requirements() -> Mapping[str, Any]:
    return _as_mapping(
        load_agent_output_protocol_contract()["repair_event_requirements"],
        field="repair_event_requirements",
    )


def repair_audit_requirements() -> Mapping[str, Any]:
    return _as_mapping(
        load_agent_output_protocol_contract()["repair_audit_requirements"],
        field="repair_audit_requirements",
    )


def legacy_deprecations() -> Mapping[str, Any]:
    return _as_mapping(load_agent_output_protocol_contract()["legacy_deprecations"], field="legacy_deprecations")
