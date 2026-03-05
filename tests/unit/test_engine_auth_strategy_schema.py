from __future__ import annotations

import json
from pathlib import Path

import jsonschema  # type: ignore[import-untyped]
import pytest
import yaml  # type: ignore[import-untyped]


def _load_schema() -> dict[str, object]:
    path = (
        Path("server")
        / "assets"
        / "schemas"
        / "engine_auth"
        / "engine_auth_strategy.schema.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _load_strategy() -> dict[str, object]:
    path = Path("server") / "assets" / "configs" / "engine_auth_strategy.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_engine_auth_strategy_yaml_matches_schema() -> None:
    schema = _load_schema()
    strategy = _load_strategy()

    jsonschema.validate(instance=strategy, schema=schema)


def test_engine_auth_strategy_schema_rejects_missing_required_fields() -> None:
    schema = _load_schema()
    strategy = _load_strategy()
    strategy.pop("engines", None)

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=strategy, schema=schema)
