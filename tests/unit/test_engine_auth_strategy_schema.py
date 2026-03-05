from __future__ import annotations

import json

import jsonschema  # type: ignore[import-untyped]
import pytest
import yaml  # type: ignore[import-untyped]

from server.config_registry import keys
from server.config_registry.registry import config_registry


def _load_schema() -> dict[str, object]:
    candidates = config_registry.engine_auth_strategy_schema_paths()
    path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    return json.loads(path.read_text(encoding="utf-8"))


def _load_strategy() -> dict[str, object]:
    engines: dict[str, object] = {}
    for engine in keys.ENGINE_KEYS:
        path = config_registry.engine_config_path(engine=engine, filename=keys.ENGINE_AUTH_STRATEGY_NAME)
        assert path.exists()
        engine_payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(engine_payload, dict)
        engines[engine] = engine_payload
    return {"version": 1, "engines": engines}


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
