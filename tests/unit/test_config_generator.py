import json
import logging
from pathlib import Path

import pytest

from server.engines.common.config.json_layer_config_generator import ConfigGenerator


def test_unknown_config_key_logs_warning(tmp_path, caplog):
    generator = ConfigGenerator()
    generator._contract_schemas_dir = tmp_path  # type: ignore[attr-defined]
    generator._engine_schemas_glob = tmp_path  # type: ignore[attr-defined]

    schema = {"known": "str"}
    (tmp_path / "schema.json").write_text(json.dumps(schema))

    output_path = tmp_path / "settings.json"
    with caplog.at_level(logging.WARNING):
        generator.generate_config(
            schema_name="schema.json",
            config_layers=[{"known": "ok", "unknown": 1}],
            output_path=output_path
        )

    assert output_path.exists()
    assert "unknown" in output_path.read_text()
    assert any("unknown" in record.message for record in caplog.records)


def test_json_schema_config_accepts_claude_env_without_unknown_key_warning(tmp_path, caplog):
    generator = ConfigGenerator()
    generator._contract_schemas_dir = tmp_path  # type: ignore[attr-defined]
    generator._engine_schemas_glob = tmp_path  # type: ignore[attr-defined]

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "env": {
                "type": "object",
                "additionalProperties": {
                    "type": "string"
                }
            },
            "sandbox": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "enabled": {"type": "boolean"}
                }
            }
        }
    }
    (tmp_path / "schema.json").write_text(json.dumps(schema), encoding="utf-8")

    output_path = tmp_path / "settings.json"
    with caplog.at_level(logging.WARNING):
        generator.generate_config(
            schema_name="schema.json",
            config_layers=[{"env": {"ANTHROPIC_MODEL": "haiku"}, "sandbox": {"enabled": True}}],
            output_path=output_path,
        )

    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["env"]["ANTHROPIC_MODEL"] == "haiku"
    assert payload["sandbox"]["enabled"] is True
    assert not caplog.records


def test_json_schema_config_rejects_invalid_claude_permission_mode(tmp_path):
    generator = ConfigGenerator()
    generator._contract_schemas_dir = tmp_path  # type: ignore[attr-defined]
    generator._engine_schemas_glob = tmp_path  # type: ignore[attr-defined]

    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "permissions": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "defaultMode": {
                        "type": "string",
                        "enum": ["bypassPermissions", "dontAsk"],
                    }
                }
            }
        }
    }
    (tmp_path / "schema.json").write_text(json.dumps(schema), encoding="utf-8")

    with pytest.raises(ValueError, match="defaultMode"):
        generator.generate_config(
            schema_name="schema.json",
            config_layers=[{"permissions": {"defaultMode": "invalid"}}],
            output_path=tmp_path / "settings.json",
        )
