from __future__ import annotations

import os

from tests.common.protocol_golden_fixture_contract import list_protocol_golden_fixtures
from tests.common.protocol_golden_fixture_extractor import list_protocol_golden_source_runs


def _engine_filter() -> str | None:
    engine_obj = os.environ.get("SKILL_RUNNER_ENGINE_INTEGRATION_ENGINE_FILTER")
    if engine_obj is None:
        return None
    engine = engine_obj.strip()
    return engine or None


def _captured_fixture_ids(*, layer: str) -> list[str]:
    engine = _engine_filter()
    fixture_ids: list[str] = []
    for item in list_protocol_golden_fixtures():
        if item.get("source") != "captured_run":
            continue
        if item.get("layer") != layer:
            continue
        item_engine = str(item.get("engine") or "")
        if engine is not None and item_engine != engine:
            continue
        fixture_id = str(item.get("fixture_id") or "").strip()
        if fixture_id:
            fixture_ids.append(fixture_id)
    return sorted(fixture_ids)


def captured_protocol_fixture_ids() -> list[str]:
    return _captured_fixture_ids(layer="protocol_core")


def captured_outcome_fixture_ids() -> list[str]:
    return _captured_fixture_ids(layer="outcome_core")


def captured_source_run_keys() -> list[str]:
    engine = _engine_filter()
    keys: list[str] = []
    for item in list_protocol_golden_source_runs():
        item_engine = str(item.get("engine") or "")
        if engine is not None and item_engine != engine:
            continue
        source_run_key = str(item.get("source_run_key") or "").strip()
        if source_run_key:
            keys.append(source_run_key)
    return sorted(keys)
