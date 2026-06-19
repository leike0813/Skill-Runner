from __future__ import annotations

import json
from pathlib import Path

import jsonschema  # type: ignore[import-untyped]
import tomlkit

from server.config_registry import keys


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_active_engine_keys_exclude_gemini_and_keep_legacy_readonly() -> None:
    assert set(keys.ENGINE_KEYS) == {"codex", "opencode", "claude", "qwen"}
    assert "gemini" in keys.LEGACY_READONLY_ENGINE_KEYS


def test_active_engine_config_layers_validate_against_schemas() -> None:
    schema_paths = {
        "claude": PROJECT_ROOT / "server/engines/claude/schemas/claude_settings_schema.json",
        "opencode": PROJECT_ROOT / "server/engines/opencode/schemas/opencode_config_schema.json",
        "qwen": PROJECT_ROOT / "server/engines/qwen/schemas/qwen_config_schema.json",
    }
    for engine, schema_path in schema_paths.items():
        schema = _load_json(schema_path)
        config_dir = PROJECT_ROOT / "server" / "engines" / engine / "config"
        for config_path in config_dir.glob("*.json"):
            jsonschema.validate(_load_json(config_path), schema)


def test_codex_config_layers_validate_against_profile_schema() -> None:
    schema = _load_json(PROJECT_ROOT / "server/engines/codex/schemas/codex_profile_schema.json")
    config_dir = PROJECT_ROOT / "server/engines/codex/config"
    for config_path in config_dir.glob("*.toml"):
        payload = dict(tomlkit.parse(config_path.read_text(encoding="utf-8")))
        jsonschema.validate(payload, schema)
