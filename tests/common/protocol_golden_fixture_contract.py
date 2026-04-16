from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, cast

import jsonschema  # type: ignore[import-untyped]

from tests.common.runtime_parser_capability_contract import (
    load_runtime_parser_capability_contract,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "protocol_golden"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"
SCHEMA_PATH = PROJECT_ROOT / "server" / "contracts" / "schemas" / "protocol_golden_fixture.schema.json"


def _as_mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"Invalid protocol golden fixture field `{field}`")
    return value


def _resolve_capability_path(capabilities: Mapping[str, Any], path: str) -> Any:
    current: Any = capabilities
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise RuntimeError(f"Unknown parser capability path `{path}`")
        current = current[part]
    return current


@lru_cache(maxsize=1)
def load_protocol_golden_fixture_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise RuntimeError(f"Protocol golden fixture manifest not found: {MANIFEST_PATH}")
    payload_obj = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload_obj, dict):
        raise RuntimeError("Protocol golden fixture manifest root must be a mapping")
    fixtures_obj = payload_obj.get("fixtures")
    if not isinstance(fixtures_obj, list):
        raise RuntimeError("Protocol golden fixture manifest must declare `fixtures` as a list")
    return payload_obj


@lru_cache(maxsize=1)
def load_protocol_golden_fixture_schema() -> dict[str, Any]:
    if not SCHEMA_PATH.exists():
        raise RuntimeError(f"Protocol golden fixture schema not found: {SCHEMA_PATH}")
    payload_obj = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload_obj, dict):
        raise RuntimeError("Protocol golden fixture schema root must be a mapping")
    return payload_obj


def protocol_golden_fixture_manifest_path() -> Path:
    return MANIFEST_PATH


def protocol_golden_fixture_schema_path() -> Path:
    return SCHEMA_PATH


def list_protocol_golden_fixtures() -> list[dict[str, Any]]:
    manifest = load_protocol_golden_fixture_manifest()
    fixtures_obj = cast(list[Any], manifest["fixtures"])
    return [dict(item) for item in fixtures_obj if isinstance(item, dict)]


def _load_fixture_blob(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_protocol_golden_fixture(fixture_id: str) -> dict[str, Any]:
    manifest_entries = list_protocol_golden_fixtures()
    entry = next((item for item in manifest_entries if item.get("fixture_id") == fixture_id), None)
    if entry is None:
        raise RuntimeError(f"Unknown protocol golden fixture `{fixture_id}`")

    relative_path_obj = entry.get("path")
    if not isinstance(relative_path_obj, str) or not relative_path_obj.strip():
        raise RuntimeError(f"Protocol golden fixture `{fixture_id}` has invalid manifest path")
    fixture_path = FIXTURE_ROOT / relative_path_obj
    if not fixture_path.exists():
        raise RuntimeError(f"Protocol golden fixture file not found: {fixture_path}")

    payload_obj = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(payload_obj, dict):
        raise RuntimeError(f"Protocol golden fixture `{fixture_id}` must be a mapping")
    jsonschema.validate(payload_obj, load_protocol_golden_fixture_schema())

    if payload_obj.get("fixture_id") != fixture_id:
        raise RuntimeError(f"Protocol golden fixture `{fixture_id}` has mismatched `fixture_id`")
    for key in ("layer", "engine", "source"):
        if payload_obj.get(key) != entry.get(key):
            raise RuntimeError(f"Protocol golden fixture `{fixture_id}` manifest mismatch for `{key}`")

    inputs = _as_mapping(payload_obj.get("inputs"), field="inputs")
    hydrated_inputs = dict(inputs)
    for field_name, target_name in (
        ("stdout_file", "stdout"),
        ("stderr_file", "stderr"),
        ("pty_output_file", "pty_output"),
    ):
        file_obj = inputs.get(field_name)
        if not isinstance(file_obj, str) or not file_obj.strip():
            continue
        blob_path = fixture_path.parent / file_obj
        if not blob_path.exists():
            raise RuntimeError(f"Fixture blob `{field_name}` not found for `{fixture_id}`: {blob_path}")
        hydrated_inputs[target_name] = _load_fixture_blob(blob_path)

    payload = dict(payload_obj)
    payload["inputs"] = hydrated_inputs
    payload["__manifest_entry__"] = dict(entry)
    payload["__fixture_path__"] = str(fixture_path)
    return payload


def fixture_supports_engine(fixture: Mapping[str, Any], *, target_engine: str | None = None) -> bool:
    fixture_engine_obj = fixture.get("engine")
    if not isinstance(fixture_engine_obj, str) or not fixture_engine_obj.strip():
        raise RuntimeError("Fixture missing valid `engine`")
    fixture_engine = fixture_engine_obj.strip()
    engine = (target_engine or fixture_engine).strip()
    if fixture_engine != "common" and engine != fixture_engine:
        return False

    requirements_obj = fixture.get("capability_requirements")
    if not isinstance(requirements_obj, list):
        raise RuntimeError("Fixture missing valid `capability_requirements`")
    if engine == "common":
        return True

    contract = load_runtime_parser_capability_contract()
    engines = _as_mapping(contract.get("engines"), field="engines")
    engine_capabilities = _as_mapping(engines.get(engine), field=f"engines.{engine}")
    for requirement_obj in requirements_obj:
        if not isinstance(requirement_obj, str) or not requirement_obj.strip():
            raise RuntimeError("Capability requirement entries must be non-empty strings")
        if _resolve_capability_path(engine_capabilities, requirement_obj.strip()) is not True:
            return False
    return True
