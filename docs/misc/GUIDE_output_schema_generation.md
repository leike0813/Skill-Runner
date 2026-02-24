# Dynamic Output Schema Generation — Guide & Example Code

## Overview

The output schema patch is dynamically generated at runtime by parsing the skill's `output.schema.json`. It produces two things:

1. A **Markdown table** describing each field (including `__SKILL_DONE__` as the first row).
2. A **JSON skeleton** example showing the expected output structure.

This generated text is appended after `patch_output_format_contract.md` (the static rules) in the patched SKILL.md.

## Example: Input → Output

### Input: `output.schema.json` (tag-regulator)

```json
{
  "type": "object",
  "required": ["metadata", "input_tags", "remove_tags", "add_tags", "suggest_tags", "provenance", "warnings", "error"],
  "properties": {
    "metadata": {
      "description": "Echo of input metadata. Free-form JSON value."
    },
    "input_tags": {
      "type": "array",
      "items": { "type": "string" }
    },
    "remove_tags": {
      "type": "array",
      "items": { "type": "string" }
    },
    "add_tags": {
      "type": "array",
      "items": { "type": "string" },
      "uniqueItems": true
    },
    "suggest_tags": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["tag", "note"],
        "properties": {
          "tag": { "type": "string" },
          "note": { "type": "string" }
        },
        "additionalProperties": false
      }
    },
    "provenance": {
      "type": "object",
      "required": ["generated_at"],
      "properties": {
        "generated_at": {
          "type": "string",
          "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$"
        }
      },
      "additionalProperties": true
    },
    "warnings": {
      "type": "array",
      "items": { "type": "string" }
    },
    "error": {
      "anyOf": [
        { "type": "null" },
        {
          "type": "object",
          "required": ["type", "message"],
          "properties": {
            "type": { "type": "string" },
            "message": { "type": "string" },
            "details": {}
          },
          "additionalProperties": true
        }
      ]
    }
  },
  "additionalProperties": false
}
```

### Expected Output (injected into SKILL.md)

```markdown
### Output Schema Specification

Your output JSON must conform to the following schema:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `__SKILL_DONE__` | boolean (`true`) | ✅ | Completion signal. Must be the first field. |
| `metadata` | any | ✅ | Echo of input metadata. Free-form JSON value. |
| `input_tags` | array of string | ✅ | |
| `remove_tags` | array of string | ✅ | |
| `add_tags` | array of string (unique) | ✅ | |
| `suggest_tags` | array of object | ✅ | Each item: `{tag: string, note: string}` |
| `provenance` | object | ✅ | Must include `generated_at` (ISO 8601 datetime string) |
| `warnings` | array of string | ✅ | |
| `error` | null or object | ✅ | If error: `{type: string, message: string}`. If success: `null` |

No additional properties are allowed.

Example output:
```json
{
  "__SKILL_DONE__": true,
  "metadata": "...",
  "input_tags": ["..."],
  "remove_tags": ["..."],
  "add_tags": ["..."],
  "suggest_tags": [{"tag": "...", "note": "..."}],
  "provenance": {"generated_at": "2025-01-01T00:00:00Z"},
  "warnings": [],
  "error": null
}
```
```

### Artifact Fields (literature-digest style)

When a field has `"x-type": "artifact"`, the description column should indicate it is an artifact path controlled by runtime:

```
| `digest_path` | string | ✅ | Artifact output path (set by runtime, see "Runtime Output Overrides" above). |
```

These fields should **not** be filtered out of the table — they must still appear in the final JSON output, but the description clarifies that their values are determined by the artifact redirection section.

---

## Example Code

```python
import json
from typing import Any, Dict, List, Optional, Tuple


def generate_output_schema_patch(schema: Dict[str, Any]) -> str:
    """
    Generate a Markdown output schema specification from output.schema.json.

    Returns a Markdown string containing:
    - A field table (with __SKILL_DONE__ as the first row)
    - A JSON skeleton example

    Args:
        schema: Parsed content of output.schema.json.
    """
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))
    additional_props = schema.get("additionalProperties", True)

    # --- Build table rows ---
    rows: List[str] = []

    # First row: __SKILL_DONE__ (always present, always required)
    rows.append(
        "| `__SKILL_DONE__` | boolean (`true`) | ✅ | Completion signal. Must be the first field. |"
    )

    # Remaining rows: from schema properties
    for field_name, field_schema in properties.items():
        type_str = _describe_type(field_schema)
        is_required = field_name in required_fields
        req_mark = "✅" if is_required else ""
        desc = _describe_field(field_name, field_schema)
        rows.append(f"| `{field_name}` | {type_str} | {req_mark} | {desc} |")

    # --- Build JSON skeleton ---
    skeleton = _build_skeleton(properties, required_fields)

    # --- Assemble Markdown ---
    lines = [
        "### Output Schema Specification",
        "",
        "Your output JSON must conform to the following schema:",
        "",
        "| Field | Type | Required | Description |",
        "|-------|------|----------|-------------|",
        *rows,
    ]

    if not additional_props:
        lines.append("")
        lines.append("No additional properties are allowed.")

    lines.extend([
        "",
        "Example output:",
        "```json",
        json.dumps(skeleton, indent=2, ensure_ascii=False),
        "```",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Type Description
# ---------------------------------------------------------------------------

def _describe_type(field_schema: Dict[str, Any]) -> str:
    """Produce a concise human-readable type string."""
    # anyOf / oneOf (e.g. null | object)
    for combo_key in ("anyOf", "oneOf"):
        if combo_key in field_schema:
            parts = [_describe_type(sub) for sub in field_schema[combo_key]]
            return " or ".join(parts)

    raw_type = field_schema.get("type")

    # type is a list (e.g. ["object", "null"])
    if isinstance(raw_type, list):
        return " or ".join(raw_type)

    if raw_type == "array":
        items = field_schema.get("items", {})
        items_type = items.get("type", "any")
        suffix = ""
        if field_schema.get("uniqueItems"):
            suffix = " (unique)"
        if items_type == "object":
            return f"array of object{suffix}"
        return f"array of {items_type}{suffix}"

    if raw_type is not None:
        return raw_type

    # No type specified → any
    return "any"


# ---------------------------------------------------------------------------
# Field Description
# ---------------------------------------------------------------------------

def _describe_field(field_name: str, field_schema: Dict[str, Any]) -> str:
    """Produce a concise description for the table."""
    # Artifact fields
    if field_schema.get("x-type") == "artifact":
        return "Artifact output path (set by runtime, see \"Runtime Output Overrides\" above)."

    # Explicit description
    desc = field_schema.get("description", "")

    # Enrich: array of object with required sub-fields
    if field_schema.get("type") == "array":
        items = field_schema.get("items", {})
        if items.get("type") == "object" and "properties" in items:
            sub_fields = ", ".join(
                f"{k}: {v.get('type', 'any')}"
                for k, v in items["properties"].items()
            )
            sub_desc = f"Each item: `{{{sub_fields}}}`"
            return f"{desc} {sub_desc}".strip() if desc else sub_desc

    # Enrich: object with required sub-fields
    if field_schema.get("type") == "object" and "required" in field_schema:
        req = field_schema["required"]
        props = field_schema.get("properties", {})
        parts = []
        for r in req:
            prop = props.get(r, {})
            hint = prop.get("type", "any")
            pattern = prop.get("pattern")
            if pattern:
                hint += f" (e.g. `\"2025-01-01T00:00:00Z\"`)" if "T" in pattern else ""
            parts.append(f"`{r}` ({hint})")
        sub_desc = "Must include " + ", ".join(parts)
        return f"{desc} {sub_desc}".strip() if desc else sub_desc

    # anyOf: null | object
    for combo_key in ("anyOf", "oneOf"):
        if combo_key in field_schema:
            variants = field_schema[combo_key]
            has_null = any(v.get("type") == "null" for v in variants)
            obj_variant = next(
                (v for v in variants if v.get("type") == "object"), None
            )
            if has_null and obj_variant and "required" in obj_variant:
                req = obj_variant["required"]
                props = obj_variant.get("properties", {})
                sub_fields = ", ".join(
                    f"{k}: {props.get(k, {}).get('type', 'any')}" for k in req
                )
                return f"If error: `{{{sub_fields}}}`. If success: `null`"

    return desc


# ---------------------------------------------------------------------------
# JSON Skeleton
# ---------------------------------------------------------------------------

def _build_skeleton(
    properties: Dict[str, Any],
    required_fields: set,
) -> Dict[str, Any]:
    """Build a JSON skeleton example with __SKILL_DONE__ as first field."""
    skeleton: Dict[str, Any] = {"__SKILL_DONE__": True}

    for field_name, field_schema in properties.items():
        skeleton[field_name] = _skeleton_value(field_schema)

    return skeleton


def _skeleton_value(field_schema: Dict[str, Any]) -> Any:
    """Generate a placeholder value for a single field."""
    # Artifact fields
    if field_schema.get("x-type") == "artifact":
        return "{{ run_dir }}/artifacts/" + (field_schema.get("x-filename") or "...")

    # anyOf / oneOf → prefer non-null variant for skeleton
    for combo_key in ("anyOf", "oneOf"):
        if combo_key in field_schema:
            variants = field_schema[combo_key]
            has_null = any(v.get("type") == "null" for v in variants)
            if has_null:
                return None
            return _skeleton_value(variants[0])

    raw_type = field_schema.get("type")

    # type is a list
    if isinstance(raw_type, list):
        if "null" in raw_type:
            return None
        return "..."

    if raw_type == "string":
        return "..."
    if raw_type == "integer":
        return 0
    if raw_type == "number":
        return 0.0
    if raw_type == "boolean":
        return False
    if raw_type == "null":
        return None

    if raw_type == "array":
        items = field_schema.get("items", {})
        if items.get("type") == "object" and "properties" in items:
            example_obj = {
                k: "..." for k in items["properties"]
            }
            return [example_obj]
        item_type = items.get("type", "string")
        return ["..."] if item_type == "string" else [f"<{item_type}>"]

    if raw_type == "object":
        props = field_schema.get("properties", {})
        if props:
            return {k: _skeleton_value(v) for k, v in props.items()}
        return {}

    # No type → freeform
    return "..."
```

---

## Integration Points in `SkillPatcher`

### New Method

Add a `generate_output_schema_patch` method to `SkillPatcher`:

```python
def generate_output_schema_patch(self, output_schema: Dict[str, Any]) -> str:
    """Generate dynamic output schema specification from output.schema.json."""
    if not output_schema or not isinstance(output_schema, dict):
        return ""
    return generate_output_schema_patch(output_schema)
```

### Where to Get the Schema

The schema is available via the skill manifest's `schemas` dictionary. In `patch_skill_md` (or at the adapter level), load it:

```python
output_schema_path_str = skill.schemas.get("output")
if output_schema_path_str:
    output_schema_file = skill.path / output_schema_path_str
    if output_schema_file.exists():
        output_schema = json.loads(output_schema_file.read_text(encoding="utf-8"))
```

### Injection Order

The output schema patch is appended **after** the static `patch_output_format_contract.md` and **before** the mode patch:

```
[Original SKILL.md]

1. Runtime Enforcement Header       ← patch_runtime_enforcement.md
2. Runtime Output Overrides         ← patch_artifact_redirection.md (if artifacts exist)
3. Output Format Contract           ← patch_output_format_contract.md (static rules)
4. Output Schema Specification      ← dynamically generated (this module)
5. Execution Mode: AUTO/INTERACTIVE ← patch_mode_auto.md or patch_mode_interactive.md
```

### Marker

Define a new marker for idempotency detection:

```python
OUTPUT_SCHEMA_PATCH_MARKER = "### Output Schema Specification"
```

This marker already appears as the first line of the generated output from `generate_output_schema_patch`.
