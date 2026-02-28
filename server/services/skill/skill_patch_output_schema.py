from __future__ import annotations

import json
from typing import Any, Dict, List


OUTPUT_SCHEMA_PATCH_MARKER = "### Output Schema Specification"
_DONE_MARKER_ROW = (
    "| `__SKILL_DONE__` | boolean (`true`) | ✅ | Completion signal. Must be the first field. |"
)


def generate_output_schema_patch(schema: Dict[str, Any]) -> str:
    if not schema or not isinstance(schema, dict):
        return ""
    properties = schema.get("properties")
    if not isinstance(properties, dict) or not properties:
        return ""
    required_fields = set(schema.get("required", []))
    additional_props = schema.get("additionalProperties", True)
    rows: List[str] = [_DONE_MARKER_ROW]

    for field_name, field_schema in properties.items():
        if not isinstance(field_name, str):
            continue
        field_schema_dict = field_schema if isinstance(field_schema, dict) else {}
        type_str = _describe_type(field_schema_dict)
        req_mark = "✅" if field_name in required_fields else ""
        desc = _describe_field(field_schema_dict)
        rows.append(f"| `{field_name}` | {type_str} | {req_mark} | {desc} |")

    skeleton = _build_skeleton(properties)
    lines = [
        OUTPUT_SCHEMA_PATCH_MARKER,
        "",
        "Your output JSON must conform to the following schema:",
        "",
        "| Field | Type | Required | Description |",
        "|-------|------|----------|-------------|",
        *rows,
    ]
    if additional_props is False:
        lines.append("")
        lines.append("No additional properties are allowed.")

    lines.extend(
        [
            "",
            "Example output:",
            "```json",
            json.dumps(skeleton, indent=2, ensure_ascii=False),
            "```",
        ]
    )
    return "\n".join(lines)


def _describe_type(field_schema: Dict[str, Any]) -> str:
    for key in ("anyOf", "oneOf"):
        combo = field_schema.get(key)
        if isinstance(combo, list) and combo:
            return " or ".join(_describe_type(item if isinstance(item, dict) else {}) for item in combo)

    raw_type = field_schema.get("type")
    if isinstance(raw_type, list) and raw_type:
        return " or ".join(str(item) for item in raw_type)
    if raw_type == "array":
        items = field_schema.get("items")
        item_schema = items if isinstance(items, dict) else {}
        item_type = item_schema.get("type", "any")
        qualifiers: List[str] = []
        if field_schema.get("uniqueItems"):
            qualifiers.append("unique")
        min_items = _as_non_negative_int(field_schema.get("minItems"))
        max_items = _as_non_negative_int(field_schema.get("maxItems"))
        if min_items is not None:
            qualifiers.append(f"min {min_items}")
        if max_items is not None:
            qualifiers.append(f"max {max_items}")
        suffix = f" ({', '.join(qualifiers)})" if qualifiers else ""
        return f"array of {item_type}{suffix}"
    if isinstance(raw_type, str):
        return raw_type
    return "any"


def _describe_field(field_schema: Dict[str, Any]) -> str:
    if field_schema.get("x-type") == "artifact":
        return (
            "Artifact output path (set by runtime, see \"Runtime Output Overrides\" above)."
        )
    desc = field_schema.get("description")
    if isinstance(desc, str) and desc.strip():
        base = desc.strip()
    else:
        base = ""

    raw_type = field_schema.get("type")
    if raw_type == "array":
        array_notes: List[str] = []
        items = field_schema.get("items")
        item_schema = items if isinstance(items, dict) else {}
        if item_schema.get("type") == "object":
            props = item_schema.get("properties")
            if isinstance(props, dict) and props:
                sub_fields = ", ".join(
                    f"{k}: {v.get('type', 'any') if isinstance(v, dict) else 'any'}"
                    for k, v in props.items()
                    if isinstance(k, str)
                )
                array_notes.append(f"Each item: `{{{sub_fields}}}`")

        min_items = _as_non_negative_int(field_schema.get("minItems"))
        max_items = _as_non_negative_int(field_schema.get("maxItems"))
        if min_items is not None and max_items is not None:
            if min_items == max_items:
                array_notes.append(f"Exactly {min_items} items.")
            else:
                array_notes.append(f"Item count: {min_items}..{max_items}.")
        elif min_items is not None:
            array_notes.append(f"At least {min_items} items.")
        elif max_items is not None:
            array_notes.append(f"At most {max_items} items.")
        if array_notes:
            return f"{base} {' '.join(array_notes)}".strip()

    if raw_type == "object":
        required = field_schema.get("required")
        properties = field_schema.get("properties")
        if isinstance(required, list) and required and isinstance(properties, dict):
            entries: List[str] = []
            for name in required:
                if not isinstance(name, str):
                    continue
                prop_schema = properties.get(name)
                prop_type = (
                    prop_schema.get("type", "any")
                    if isinstance(prop_schema, dict)
                    else "any"
                )
                entries.append(f"`{name}` ({prop_type})")
            if entries:
                req_desc = f"Must include {', '.join(entries)}"
                return f"{base} {req_desc}".strip()

    for key in ("anyOf", "oneOf"):
        combo = field_schema.get(key)
        if not isinstance(combo, list):
            continue
        has_null = any(isinstance(item, dict) and item.get("type") == "null" for item in combo)
        object_variant = next(
            (
                item
                for item in combo
                if isinstance(item, dict) and item.get("type") == "object"
            ),
            None,
        )
        if has_null and isinstance(object_variant, dict):
            required = object_variant.get("required")
            properties = object_variant.get("properties")
            if isinstance(required, list) and required and isinstance(properties, dict):
                fields = ", ".join(
                    f"{name}: {properties.get(name, {}).get('type', 'any') if isinstance(properties.get(name), dict) else 'any'}"
                    for name in required
                    if isinstance(name, str)
                )
                variant_desc = f"If error: `{{{fields}}}`. If success: `null`"
                return f"{base} {variant_desc}".strip()
    return base


def _build_skeleton(properties: Dict[str, Any]) -> Dict[str, Any]:
    skeleton: Dict[str, Any] = {"__SKILL_DONE__": True}
    for field_name, field_schema in properties.items():
        if not isinstance(field_name, str):
            continue
        skeleton[field_name] = _skeleton_value(field_schema if isinstance(field_schema, dict) else {})
    return skeleton


def _skeleton_value(field_schema: Dict[str, Any]) -> Any:
    if field_schema.get("x-type") == "artifact":
        filename = field_schema.get("x-filename")
        if isinstance(filename, str) and filename.strip():
            return f"{{{{ run_dir }}}}/artifacts/{filename.strip()}"
        return "{{ run_dir }}/artifacts/..."

    for key in ("anyOf", "oneOf"):
        combo = field_schema.get(key)
        if isinstance(combo, list) and combo:
            if any(isinstance(item, dict) and item.get("type") == "null" for item in combo):
                return None
            first = combo[0]
            return _skeleton_value(first if isinstance(first, dict) else {})

    raw_type = field_schema.get("type")
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
        items = field_schema.get("items")
        item_schema = items if isinstance(items, dict) else {}
        item_count = _array_item_count_for_skeleton(field_schema)
        return [_skeleton_value(item_schema) for _ in range(item_count)]
    if raw_type == "object":
        props = field_schema.get("properties")
        if isinstance(props, dict):
            return {
                key: _skeleton_value(value if isinstance(value, dict) else {})
                for key, value in props.items()
                if isinstance(key, str)
            }
        return {}
    return "..."


def _as_non_negative_int(value: Any) -> int | None:
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _array_item_count_for_skeleton(field_schema: Dict[str, Any]) -> int:
    min_items = _as_non_negative_int(field_schema.get("minItems"))
    max_items = _as_non_negative_int(field_schema.get("maxItems"))
    lower = min_items if min_items is not None else 0

    if max_items is not None and max_items < lower:
        return max_items
    if lower > 0:
        return lower
    if max_items is not None:
        return 1 if max_items >= 1 else 0
    return 1
