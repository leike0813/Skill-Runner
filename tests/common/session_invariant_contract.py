from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Set, Tuple

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / "docs" / "contracts" / "session_fcmp_invariants.yaml"


def _as_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Invalid invariant contract field `{field}`")
    return value.strip()


def _as_mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"Invalid invariant contract field `{field}`")
    return value


def _as_list(value: Any, *, field: str) -> List[Any]:
    if not isinstance(value, list):
        raise RuntimeError(f"Invalid invariant contract field `{field}`")
    return value


def _extract_transition_rows(rows: Iterable[Any], *, field: str) -> Set[Tuple[str, str, str]]:
    triples: Set[Tuple[str, str, str]] = set()
    for row in rows:
        mapping = _as_mapping(row, field=field)
        source = _as_str(mapping.get("source"), field=f"{field}.source")
        event = _as_str(mapping.get("event"), field=f"{field}.event")
        target = _as_str(mapping.get("target"), field=f"{field}.target")
        triples.add((source, event, target))
    return triples


def _extract_state_changed_rows(rows: Iterable[Any], *, field: str) -> Set[Tuple[str, str, str]]:
    triples: Set[Tuple[str, str, str]] = set()
    for row in rows:
        mapping = _as_mapping(row, field=field)
        source = _as_str(mapping.get("source"), field=f"{field}.source")
        target = _as_str(mapping.get("target"), field=f"{field}.target")
        trigger = _as_str(mapping.get("trigger"), field=f"{field}.trigger")
        triples.add((source, target, trigger))
    return triples


@lru_cache(maxsize=1)
def load_session_invariant_contract() -> Dict[str, Any]:
    if not CONTRACT_PATH.exists():
        raise RuntimeError(f"Invariant contract file not found: {CONTRACT_PATH}")
    payload_obj = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload_obj, dict):
        raise RuntimeError("Invariant contract root must be a mapping")

    canonical = _as_mapping(payload_obj.get("canonical"), field="canonical")
    _as_str(canonical.get("initial_state"), field="canonical.initial_state")
    _as_list(canonical.get("states"), field="canonical.states")
    _as_list(canonical.get("terminal_states"), field="canonical.terminal_states")
    _as_list(payload_obj.get("transitions"), field="transitions")

    fcmp_mapping = _as_mapping(payload_obj.get("fcmp_mapping"), field="fcmp_mapping")
    _as_list(fcmp_mapping.get("state_changed"), field="fcmp_mapping.state_changed")
    _as_list(fcmp_mapping.get("paired_events"), field="fcmp_mapping.paired_events")
    _as_list(payload_obj.get("ordering_rules"), field="ordering_rules")
    return payload_obj


def contract_path() -> Path:
    return CONTRACT_PATH


def initial_state() -> str:
    contract = load_session_invariant_contract()
    canonical = _as_mapping(contract["canonical"], field="canonical")
    return _as_str(canonical["initial_state"], field="canonical.initial_state")


def canonical_states() -> Set[str]:
    contract = load_session_invariant_contract()
    canonical = _as_mapping(contract["canonical"], field="canonical")
    return {
        _as_str(item, field="canonical.states[]")
        for item in _as_list(canonical["states"], field="canonical.states")
    }


def terminal_states() -> Set[str]:
    contract = load_session_invariant_contract()
    canonical = _as_mapping(contract["canonical"], field="canonical")
    return {
        _as_str(item, field="canonical.terminal_states[]")
        for item in _as_list(canonical["terminal_states"], field="canonical.terminal_states")
    }


def transition_tuples() -> Set[Tuple[str, str, str]]:
    contract = load_session_invariant_contract()
    return _extract_transition_rows(
        _as_list(contract["transitions"], field="transitions"),
        field="transitions[]",
    )


def transition_index() -> Dict[Tuple[str, str], str]:
    return {(source, event): target for source, event, target in transition_tuples()}


def fcmp_state_changed_tuples() -> Set[Tuple[str, str, str]]:
    contract = load_session_invariant_contract()
    fcmp_mapping = _as_mapping(contract["fcmp_mapping"], field="fcmp_mapping")
    return _extract_state_changed_rows(
        _as_list(fcmp_mapping["state_changed"], field="fcmp_mapping.state_changed"),
        field="fcmp_mapping.state_changed[]",
    )


def paired_event_rules() -> Dict[str, Tuple[str, str, str]]:
    contract = load_session_invariant_contract()
    fcmp_mapping = _as_mapping(contract["fcmp_mapping"], field="fcmp_mapping")
    rows = _as_list(fcmp_mapping["paired_events"], field="fcmp_mapping.paired_events")
    rules: Dict[str, Tuple[str, str, str]] = {}
    for row in rows:
        mapping = _as_mapping(row, field="fcmp_mapping.paired_events[]")
        event_type = _as_str(mapping.get("event_type"), field="fcmp_mapping.paired_events[].event_type")
        required_state_change = _as_mapping(
            mapping.get("required_state_change"),
            field="fcmp_mapping.paired_events[].required_state_change",
        )
        source = _as_str(
            required_state_change.get("source"),
            field="fcmp_mapping.paired_events[].required_state_change.source",
        )
        target = _as_str(
            required_state_change.get("target"),
            field="fcmp_mapping.paired_events[].required_state_change.target",
        )
        trigger = _as_str(
            required_state_change.get("trigger"),
            field="fcmp_mapping.paired_events[].required_state_change.trigger",
        )
        rules[event_type] = (source, target, trigger)
    return rules


def ordering_rules() -> Set[str]:
    contract = load_session_invariant_contract()
    rules: Set[str] = set()
    for row in _as_list(contract["ordering_rules"], field="ordering_rules"):
        mapping = _as_mapping(row, field="ordering_rules[]")
        rules.add(_as_str(mapping.get("rule"), field="ordering_rules[].rule"))
    return rules
