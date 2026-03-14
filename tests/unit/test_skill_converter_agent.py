import json
from pathlib import Path

from jsonschema import Draft7Validator  # type: ignore[import-untyped]

OUTPUT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "skill-converter-agent"
    / "assets"
    / "output.schema.json"
)


def test_output_schema_not_convertible_rejects_package_fields() -> None:
    schema = json.loads(OUTPUT_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)
    valid_payload = {
        "status": "failed",
        "classification": "not_convertible",
        "failure_reason": "requires interactive human decisions",
    }
    assert list(validator.iter_errors(valid_payload)) == []

    invalid_payload = {
        "status": "failed",
        "classification": "not_convertible",
        "failure_reason": "requires interactive human decisions",
        "converted_skill_directory_path": "/tmp/converted_skill",
    }
    errors = list(validator.iter_errors(invalid_payload))
    assert errors


def test_output_schema_success_classes_require_package_fields() -> None:
    schema = json.loads(OUTPUT_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)
    missing_fields_payload = {
        "status": "succeeded",
        "classification": "ready_for_auto",
    }
    errors = list(validator.iter_errors(missing_fields_payload))
    assert errors

    valid_payload = {
        "status": "succeeded",
        "classification": "ready_for_auto",
        "converted_skill_package_path": "artifacts/converted_skill.zip",
        "conversion_report_path": "artifacts/conversion_report.md",
    }
    assert list(validator.iter_errors(valid_payload)) == []
