from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import yaml  # type: ignore[import-untyped]

from server.config_registry.registry import config_registry
from server.services.skill.skill_patch_templates import (
    OUTPUT_CONTRACT_DETAILS_TEMPLATE,
    OUTPUT_CONTRACT_INTERACTIVE_PENDING_TEMPLATE,
    load_template_content,
)


OUTPUT_CONTRACT_DETAILS_MARKER = OUTPUT_CONTRACT_DETAILS_TEMPLATE.marker
_DONE_MARKER_ROW = (
    "| `__SKILL_DONE__` | boolean (`true`) | ✅ | Completion signal. Must be the first field. |"
)


def build_output_contract_details_markdown(
    schema: Dict[str, Any],
    *,
    schema_artifact_relpath: str | None = None,
    pending_branch_note: str | None = None,
    compatibility_note: str | None = None,
    example_payload: Dict[str, Any] | None = None,
) -> str:
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
        if field_name == "__SKILL_DONE__":
            continue
        field_schema_dict = field_schema if isinstance(field_schema, dict) else {}
        type_str = _describe_type(field_schema_dict)
        req_mark = "✅" if field_name in required_fields else ""
        desc = _describe_field(field_schema_dict)
        rows.append(f"| `{field_name}` | {type_str} | {req_mark} | {desc} |")

    schema_artifact_block = ""
    if isinstance(schema_artifact_relpath, str) and schema_artifact_relpath.strip():
        schema_artifact_block = (
            f"Run-scoped machine schema artifact: `{schema_artifact_relpath.strip()}`.\n\n"
        )
    compatibility_note_block = ""
    if isinstance(compatibility_note, str) and compatibility_note.strip():
        compatibility_note_block = f"{compatibility_note.strip()}\n\n"
    pending_branch_block = ""
    if isinstance(pending_branch_note, str) and pending_branch_note.strip():
        pending_branch_block = (
            "#### Pending Branch Contract\n\n"
            f"{pending_branch_note.strip()}\n\n"
        )
    additional_properties_block = (
        "\n\nNo additional properties are allowed." if additional_props is False else ""
    )
    return _render_template(
        OUTPUT_CONTRACT_DETAILS_TEMPLATE,
        {
            "schema_artifact_block": schema_artifact_block,
            "pending_branch_block": pending_branch_block,
            "compatibility_note_block": compatibility_note_block,
            "field_rows": "\n".join(rows),
            "additional_properties_block": additional_properties_block,
            "example_json": json.dumps(
                example_payload if isinstance(example_payload, dict) else build_schema_example_payload(schema),
                indent=2,
                ensure_ascii=False,
            ),
        },
    )


def build_interactive_pending_contract_note(
    *,
    include_final_example: bool,
) -> str:
    contract = _load_ui_hints_contract()
    kind_values = contract["kinds"]
    options_fields = contract["options_fields"]
    files_fields = contract["files_fields"]
    final_example = {
        "__SKILL_DONE__": True,
        "result_field": "...",
    }
    pending_example = {
        "__SKILL_DONE__": False,
        "message": "请选择下一步。",
        "ui_hints": {
            "kind": "choose_one",
            "hint": "请选择最符合当前需求的一项。",
            "options": [
                {"label": "继续", "value": "continue"},
                {"label": "先澄清问题", "value": "clarify"},
            ],
        },
    }
    final_example_block = ""
    if include_final_example:
        final_example_block = (
            "\nFinal branch example:\n"
            "```json\n"
            f"{json.dumps(final_example, ensure_ascii=False, indent=2)}\n"
            "```\n"
        )
    return _render_template(
        OUTPUT_CONTRACT_INTERACTIVE_PENDING_TEMPLATE,
        {
            "kind_values": f"`{' | '.join(kind_values)}`",
            "options_fields": options_fields,
            "files_fields": files_fields,
            "final_example_block": final_example_block,
            "pending_example_json": json.dumps(pending_example, ensure_ascii=False, indent=2),
        },
    )


def build_codex_compatibility_note(
    *,
    execution_mode: str,
) -> str:
    lines = [
        "#### Engine Compatibility Notes",
        "",
        "Codex structured output compatibility contract:",
        "- This engine uses a compatibility schema derived from the canonical runner contract.",
        "- Return exactly one JSON object that matches the machine schema artifact below.",
        "- All listed fields are required for Codex compatibility.",
        "- Inactive branch fields must be explicit `null` values.",
    ]
    if execution_mode == "interactive":
        lines.extend(
            [
                "- If `__SKILL_DONE__` is `true`, business result fields must be populated and `message` / `ui_hints` must be `null`.",
                "- If `__SKILL_DONE__` is `false`, `message` and `ui_hints` must be populated and business result fields must be `null`.",
                "- Do not omit inactive branch fields; emit `null` instead.",
            ]
        )
    return "\n".join(lines)


def build_codex_pending_branch_note(*, final_result_fields: List[str]) -> str:
    pending_example: Dict[str, Any] = {
        "__SKILL_DONE__": False,
        "message": "Please choose the next step.",
        "ui_hints": {
            "kind": "choose_one",
            "prompt": None,
            "hint": "Pick one option.",
            "options": [{"label": "Continue", "value": "continue"}],
            "files": None,
        },
    }
    for field_name in final_result_fields:
        pending_example[field_name] = None
    lines = [
        "- Return the pending branch only when user input is genuinely required before the task can continue.",
        "- `__SKILL_DONE__`: must be `false`.",
        "- `message`: required non-empty string shown directly to the user.",
        "- `ui_hints`: required object for optional rendering hints.",
        "- Inactive business-result fields must be emitted as explicit `null` values.",
        "- Inactive optional `ui_hints` subfields should also be emitted as explicit `null` values when present in the compat schema.",
        "",
        "Pending branch example:",
        "```json",
        json.dumps(pending_example, indent=2, ensure_ascii=False),
        "```",
    ]
    return "\n".join(lines)


def build_schema_example_payload(schema: Dict[str, Any]) -> Dict[str, Any]:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    return _build_skeleton(properties)


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
    if field_schema.get("x-type") in {"artifact", "file"}:
        return (
            "Artifact output path. Prefer writing final deliverables under `<cwd>/artifacts/`; runtime resolves the final path into a bundle-relative path."
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
        if field_name == "__SKILL_DONE__":
            continue
        skeleton[field_name] = _skeleton_value(field_schema if isinstance(field_schema, dict) else {})
    return skeleton


def _skeleton_value(field_schema: Dict[str, Any]) -> Any:
    if field_schema.get("x-type") in {"artifact", "file"}:
        return "artifacts/..."

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


def _ask_user_contract_path() -> Path | None:
    candidates = config_registry.ask_user_schema_paths()
    return next((path for path in candidates if path.exists()), None)


def _load_ui_hints_contract() -> dict[str, Any]:
    fallback = {
        "kinds": ["open_text", "choose_one", "confirm", "upload_files"],
        "options_fields": "`label` and `value`",
        "files_fields": "`name`, `required`, `hint`, and `accept`",
    }
    contract_path = _ask_user_contract_path()
    if contract_path is None:
        return fallback
    try:
        payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return fallback
    if not isinstance(payload, dict):
        return fallback
    ask_user_obj = payload.get("ask_user")
    if not isinstance(ask_user_obj, dict):
        return fallback
    kind_values = fallback["kinds"]
    kind_obj = ask_user_obj.get("kind")
    if isinstance(kind_obj, dict):
        enum_obj = kind_obj.get("enum")
        if isinstance(enum_obj, list):
            parsed = [
                str(item).strip()
                for item in enum_obj
                if isinstance(item, str) and item.strip()
            ]
            if parsed:
                kind_values = parsed
    options_fields = fallback["options_fields"]
    options_obj = ask_user_obj.get("options")
    if isinstance(options_obj, dict):
        item_obj = options_obj.get("item")
        if isinstance(item_obj, dict):
            option_keys = [str(key) for key in item_obj.keys() if isinstance(key, str)]
            if option_keys:
                options_fields = ", ".join(f"`{key}`" for key in option_keys)
    files_fields = fallback["files_fields"]
    files_obj = ask_user_obj.get("files")
    if isinstance(files_obj, dict):
        item_obj = files_obj.get("item")
        if isinstance(item_obj, dict):
            file_keys = [str(key) for key in item_obj.keys() if isinstance(key, str)]
            if file_keys:
                files_fields = ", ".join(f"`{key}`" for key in file_keys)
    return {
        "kinds": kind_values,
        "options_fields": options_fields,
        "files_fields": files_fields,
    }


def _render_template(template: Any, values: Dict[str, str]) -> str:
    content = load_template_content(template)
    for key, value in values.items():
        content = content.replace(f"{{{key}}}", value)
    return content
