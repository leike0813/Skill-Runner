from __future__ import annotations

from typing import Any

from tests.common.protocol_golden_fixture_contract import (
    fixture_supports_engine,
    load_protocol_golden_fixture,
    list_protocol_golden_fixtures,
)
from tests.unit.auth_detection_test_utils import load_sample


def list_fixture_ids() -> list[str]:
    return [
        str(item["fixture_id"])
        for item in list_protocol_golden_fixtures()
        if isinstance(item.get("fixture_id"), str)
    ]


def load_fixture(fixture_id: str) -> dict[str, Any]:
    return load_protocol_golden_fixture(fixture_id)


def load_fixture_if_supported(
    fixture_id: str,
    *,
    target_engine: str | None = None,
) -> dict[str, Any] | None:
    fixture = load_fixture(fixture_id)
    if not fixture_supports_engine(fixture, target_engine=target_engine):
        return None
    return fixture


def load_auth_detection_sample_bridge(engine: str, sample_id: str) -> dict[str, Any]:
    return load_sample(engine, sample_id)
