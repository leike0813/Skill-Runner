import json
import logging
from pathlib import Path

from server.engines.common.config.json_layer_config_generator import ConfigGenerator


def test_unknown_config_key_logs_warning(tmp_path, caplog):
    generator = ConfigGenerator()
    generator.schemas_dir = tmp_path

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
