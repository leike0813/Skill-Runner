from pathlib import Path

import yaml


def test_ask_user_schema_is_repositioned_as_ui_hints_vocabulary() -> None:
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "server"
        / "contracts"
        / "schemas"
        / "ask_user.schema.yaml"
    )
    payload = yaml.safe_load(schema_path.read_text(encoding="utf-8"))

    assert payload["name"] == "ask_user_ui_hints_vocabulary"
    assert payload["role"] == "ui_hints_capability_source"
    assert payload["fallback_prompt"] == "Please reply to continue."
    assert payload["ask_user"]["kind"]["enum"] == [
        "open_text",
        "choose_one",
        "confirm",
        "upload_files",
    ]
    assert "<ASK_USER_YAML>" in payload["legacy_compatibility"]["deprecated_primary_protocols"]
