from __future__ import annotations

import json
from typing import cast

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
    engines = cast(dict[str, object], strategy["engines"])
    kilo = engines["kilo"]
    assert isinstance(kilo, dict)
    assert "providers" in kilo


def test_engine_auth_strategy_schema_rejects_missing_required_fields() -> None:
    schema = _load_schema()
    strategy = _load_strategy()
    strategy.pop("engines", None)

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=strategy, schema=schema)


def test_engine_auth_strategy_schema_accepts_session_behavior_extension() -> None:
    schema = _load_schema()
    strategy = _load_strategy()
    engines = cast(dict[str, object], strategy["engines"])
    kilo = engines["kilo"]
    assert isinstance(kilo, dict)
    providers = kilo["providers"]
    assert isinstance(providers, dict)
    kilo_gateway = providers["kilo"]
    assert isinstance(kilo_gateway, dict)
    transports = kilo_gateway["transports"]
    assert isinstance(transports, dict)
    oauth_proxy = transports["oauth_proxy"]
    assert isinstance(oauth_proxy, dict)

    oauth_proxy["session_behavior"] = {
        "input_required": False,
        "polling_start": "immediate",
    }

    jsonschema.validate(instance=strategy, schema=schema)


def test_engine_auth_strategy_schema_accepts_kilo_provider_aware_policy() -> None:
    schema = _load_schema()
    strategy = _load_strategy()
    engines = cast(dict[str, object], strategy["engines"])
    kilo = engines["kilo"]
    assert isinstance(kilo, dict)
    providers = kilo["providers"]
    assert isinstance(providers, dict)
    assert "kilo" in providers

    jsonschema.validate(instance=strategy, schema=schema)


def test_engine_auth_strategy_schema_rejects_kilo_disabled_policy() -> None:
    schema = _load_schema()
    strategy = _load_strategy()
    engines = cast(dict[str, object], strategy["engines"])
    engines["kilo"] = {"enabled": False}

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=strategy, schema=schema)


def test_engine_auth_strategy_schema_rejects_kilo_engine_scoped_policy() -> None:
    schema = _load_schema()
    strategy = _load_strategy()
    engines = cast(dict[str, object], strategy["engines"])
    engines["kilo"] = {
        "in_conversation": {
            "transport": "oauth_proxy",
            "methods": ["callback"],
        },
        "providers": {
            "oauth_proxy": {
                "transports": {
                    "oauth_proxy": {
                        "methods": ["callback"],
                        "driver": {
                            "start_method": "auth",
                            "execution_mode": "protocol_proxy",
                        },
                    }
                },
            }
        },
    }

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=strategy, schema=schema)
