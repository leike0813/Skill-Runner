from __future__ import annotations

import json
from typing import Any

from server.runtime.adapter.types import RuntimeAssistantMessage, RuntimeProcessEvent, RuntimeStreamRawRef


def map_content_block(
    block: dict[str, Any],
    *,
    raw_ref: RuntimeStreamRawRef,
    tool_use_by_id: dict[str, dict[str, Any]],
) -> RuntimeAssistantMessage | RuntimeProcessEvent | None:
    """Map engine-neutral thinking/text/tool blocks without owning stream semantics."""
    kind = str(block.get("type") or block.get("kind") or "").lower()
    if kind in {"text", "assistant.text"}:
        text = block.get("text") or block.get("content")
        return {"text": text, "raw_ref": raw_ref} if isinstance(text, str) and text.strip() else None
    if kind in {"thinking", "reasoning", "assistant.thinking"}:
        text = block.get("thinking") or block.get("text") or block.get("content")
        if not isinstance(text, str) or not text.strip():
            return None
        return {"process_type": "reasoning", "message_id": f"thinking_{raw_ref['byte_from']}", "summary": " ".join(text.split())[:220], "classification": "reasoning", "text": text, "raw_ref": raw_ref, "details": {"item_type": "thinking"}}
    if kind in {"tool_use", "assistant.tool_use"}:
        name = str(block.get("name") or "tool_use")
        tool_id = str(block.get("id") or block.get("tool_use_id") or "").strip()
        tool_input = block.get("input")
        tool_use_by_id[tool_id] = {"name": name, "input": tool_input}
        text = json.dumps(tool_input, ensure_ascii=False) if tool_input is not None else None
        return {"process_type": "tool_call", "message_id": tool_id or name, "summary": name, "classification": "tool_call", "text": text, "raw_ref": raw_ref, "details": {"item_type": "tool_use", "tool_name": name, "input": tool_input}}
    if kind in {"tool_result", "user.tool_result"}:
        tool_id = str(block.get("tool_use_id") or block.get("id") or "").strip()
        source = tool_use_by_id.get(tool_id, {})
        content = block.get("content")
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False) if content is not None else None
        return {"process_type": "tool_call", "message_id": tool_id or str(source.get("name") or "tool_result"), "summary": str(source.get("name") or "tool_result"), "classification": "tool_call", "text": text, "raw_ref": raw_ref, "details": {"item_type": "tool_result", "tool_use_id": tool_id or None}}
    return None
