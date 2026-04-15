from __future__ import annotations

import json
from typing import Any

from server.runtime.common.ask_user_text import normalize_interaction_text
from server.runtime.protocol.parse_utils import extract_fenced_or_plain_json, extract_json_document_with_span


def _extract_structured_payload(text: str) -> dict[str, Any] | None:
    parsed = extract_fenced_or_plain_json(text)
    if isinstance(parsed, dict):
        return parsed
    extracted = extract_json_document_with_span(text)
    if extracted is None:
        return None
    payload, _, _ = extracted
    return payload if isinstance(payload, dict) else None


def _markdown_scalar(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return "`null`"
    if isinstance(value, bool):
        return "`true`" if value else "`false`"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"`{value}`"
    return f"`{json.dumps(value, ensure_ascii=False, separators=(',', ':'))}`"


def _append_markdown_lines(lines: list[str], value: Any, indent: int, *, key: str | None = None) -> None:
    prefix = "  " * indent + "- "
    if isinstance(value, dict):
        if key is not None:
            lines.append(f"{prefix}`{key}`:")
        child_indent = indent + 1 if key is not None else indent
        if not value:
            lines.append(f"{'  ' * child_indent}- `_empty object_`")
            return
        for child_key, child_value in value.items():
            _append_markdown_lines(lines, child_value, child_indent, key=str(child_key))
        return
    if isinstance(value, list):
        if key is not None:
            lines.append(f"{prefix}`{key}`:")
        child_indent = indent + 1 if key is not None else indent
        if not value:
            lines.append(f"{'  ' * child_indent}- `_empty list_`")
            return
        for item in value:
            _append_markdown_lines(lines, item, child_indent)
        return
    if key is not None:
        lines.append(f"{prefix}`{key}`: {_markdown_scalar(value)}")
        return
    lines.append(f"{prefix}{_markdown_scalar(value)}")


def structured_payload_to_markdown(payload: dict[str, Any]) -> str:
    if not payload:
        return "- `_no structured result fields_`"
    lines: list[str] = []
    for key, value in payload.items():
        _append_markdown_lines(lines, value, 0, key=str(key))
    return "\n".join(lines)


def derive_assistant_final_display(
    *,
    text: str,
    pending_interaction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_text = normalize_interaction_text(text)
    structured_payload = _extract_structured_payload(normalized_text)
    if isinstance(structured_payload, dict):
        marker = structured_payload.get("__SKILL_DONE__")
        if marker is False:
            message_obj = structured_payload.get("message")
            message = normalize_interaction_text(message_obj) if isinstance(message_obj, str) else ""
            if message:
                return {
                    "display_text": message,
                    "display_format": "plain_text",
                    "display_origin": "pending_branch",
                    "structured_payload": structured_payload,
                }
        if marker is True:
            final_payload = {
                key: value for key, value in structured_payload.items() if key != "__SKILL_DONE__"
            }
            return {
                "display_text": structured_payload_to_markdown(final_payload),
                "display_format": "markdown",
                "display_origin": "final_branch",
                "structured_payload": final_payload,
            }

    return {
        "display_text": normalized_text,
        "display_format": "plain_text",
        "display_origin": "repair_fallback" if isinstance(pending_interaction, dict) else "raw_text",
    }
