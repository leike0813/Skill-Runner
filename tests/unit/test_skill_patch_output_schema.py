import json

from jsonschema import validate

from server.services.skill.skill_patch_output_schema import (
    OUTPUT_SCHEMA_PATCH_MARKER,
    generate_output_schema_patch,
)


def test_generate_output_schema_patch_simple_object():
    schema = {
        "type": "object",
        "required": ["value"],
        "properties": {
            "value": {"type": "string", "description": "result value"},
        },
        "additionalProperties": False,
    }
    patch = generate_output_schema_patch(schema)
    assert OUTPUT_SCHEMA_PATCH_MARKER in patch
    assert "| `__SKILL_DONE__` | boolean (`true`) | ✅ |" in patch
    assert "| `value` | string | ✅ | result value |" in patch
    assert "No additional properties are allowed." in patch


def test_generate_output_schema_patch_handles_anyof_object_or_null():
    schema = {
        "type": "object",
        "required": ["error"],
        "properties": {
            "error": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "required": ["type", "message"],
                        "properties": {
                            "type": {"type": "string"},
                            "message": {"type": "string"},
                        },
                    },
                ]
            }
        },
    }
    patch = generate_output_schema_patch(schema)
    assert "null or object" in patch
    assert "If error: `{type: string, message: string}`. If success: `null`" in patch


def test_generate_output_schema_patch_handles_array_object_description():
    schema = {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "tag": {"type": "string"},
                        "note": {"type": "string"},
                    },
                },
            }
        },
    }
    patch = generate_output_schema_patch(schema)
    assert "array of object" in patch
    assert "Each item: `{tag: string, note: string}`" in patch


def test_generate_output_schema_patch_artifact_field_description_and_skeleton():
    schema = {
        "type": "object",
        "properties": {
            "digest_path": {
                "type": "string",
                "x-type": "artifact",
                "x-filename": "digest.md",
            }
        },
    }
    patch = generate_output_schema_patch(schema)
    assert "Artifact output path (set by runtime, see \"Runtime Output Overrides\" above)." in patch
    assert "{{ run_dir }}/artifacts/digest.md" in patch


def test_generate_output_schema_patch_array_item_count_constraints_and_valid_skeleton():
    schema = {
        "type": "object",
        "required": ["tags"],
        "properties": {
            "tags": {
                "type": "array",
                "minItems": 2,
                "maxItems": 3,
                "items": {"type": "string"},
            }
        },
    }
    patch = generate_output_schema_patch(schema)
    assert "array of string (min 2, max 3)" in patch
    assert "Item count: 2..3." in patch

    skeleton = _extract_json_skeleton(patch)
    validate(instance=skeleton, schema=schema)
    assert len(skeleton["tags"]) == 2


def _extract_json_skeleton(patch: str) -> dict:
    start_marker = "```json\n"
    end_marker = "\n```"
    start = patch.index(start_marker) + len(start_marker)
    end = patch.index(end_marker, start)
    return json.loads(patch[start:end])
