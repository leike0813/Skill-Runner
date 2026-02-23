from __future__ import annotations

import json
import re
from typing import Any

from ..adapters.base import RuntimeAssistantMessage, RuntimeStreamRawRow


SCRIPT_STARTED_PREFIX = "Script started on "
SCRIPT_DONE_PREFIX = "Script done on "
FENCED_JSON_RE = re.compile(r"```json\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", re.IGNORECASE)
JSON_OBJECT_RE = re.compile(r"(\{[\s\S]*\}|\[[\s\S]*\])")
SESSION_ID_PATTERNS = (
    re.compile(r'"thread_id"\s*:\s*"([^"]+)"'),
    re.compile(r'"session_id"\s*:\s*"([^"]+)"'),
    re.compile(r"""["']?session-id["']?\s*:\s*["']([^"']+)["']"""),
    re.compile(r'"sessionID"\s*:\s*"([^"]+)"'),
)


def stream_lines_with_offsets(stream: str, raw: bytes) -> list[RuntimeStreamRawRow]:
    lines: list[RuntimeStreamRawRow] = []
    cursor = 0
    for chunk in raw.splitlines(keepends=True):
        next_cursor = cursor + len(chunk)
        text = chunk.rstrip(b"\r\n").decode("utf-8", errors="replace")
        lines.append(
            {
                "stream": stream,
                "line": text,
                "byte_from": cursor,
                "byte_to": next_cursor,
            }
        )
        cursor = next_cursor
    return lines


def strip_runtime_script_envelope(lines: list[RuntimeStreamRawRow]) -> list[RuntimeStreamRawRow]:
    filtered: list[RuntimeStreamRawRow] = []
    for row in lines:
        line = str(row.get("line", ""))
        if line.startswith(SCRIPT_STARTED_PREFIX) and "[COMMAND=" in line:
            continue
        if line.startswith(SCRIPT_DONE_PREFIX) and "[COMMAND_EXIT_CODE=" in line:
            continue
        filtered.append(row)
    return filtered


def collect_json_parse_errors(
    lines: list[RuntimeStreamRawRow],
) -> tuple[list[dict[str, Any]], list[RuntimeStreamRawRow]]:
    records: list[dict[str, Any]] = []
    raw_rows: list[RuntimeStreamRawRow] = []
    for row in lines:
        line = str(row.get("line", "")).strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(
                    {
                        "payload": payload,
                        "stream": row["stream"],
                        "byte_from": int(row["byte_from"]),
                        "byte_to": int(row["byte_to"]),
                    }
                )
            else:
                raw_rows.append(row)
        except json.JSONDecodeError:
            raw_rows.append(row)
    return records, raw_rows


def dedup_assistant_messages(messages: list[RuntimeAssistantMessage]) -> list[RuntimeAssistantMessage]:
    deduped: list[RuntimeAssistantMessage] = []
    seen: set[str] = set()
    for item in messages:
        text = item.get("text")
        if not isinstance(text, str):
            continue
        normalized = text.strip()
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(item)
    return deduped


def find_session_id(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("thread_id", "session_id", "session-id", "sessionID"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for child in value.values():
            found = find_session_id(child)
            if found:
                return found
        return None
    if isinstance(value, list):
        for item in value:
            found = find_session_id(item)
            if found:
                return found
    return None


def find_session_id_in_text(text: str) -> str | None:
    if not isinstance(text, str) or not text:
        return None
    for pattern in SESSION_ID_PATTERNS:
        matches = pattern.findall(text)
        if not matches:
            continue
        candidate = matches[-1]
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def extract_fenced_or_plain_json(text: str) -> Any | None:
    fenced = FENCED_JSON_RE.search(text)
    if fenced:
        raw = fenced.group(1)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    match = JSON_OBJECT_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _scan_json_document_end(text: str, start: int) -> int | None:
    if start < 0 or start >= len(text):
        return None
    opening = text[start]
    if opening not in "{[":
        return None
    expected_closing = "}" if opening == "{" else "]"
    stack: list[str] = [expected_closing]
    in_string = False
    escaped = False
    for idx in range(start + 1, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
                continue
            if ch == "\\":
                escaped = True
                continue
            if ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            stack.append("}")
            continue
        if ch == "[":
            stack.append("]")
            continue
        if ch in "}]":
            if not stack or ch != stack[-1]:
                return None
            stack.pop()
            if not stack:
                return idx + 1
    return None


def extract_json_document_with_span(text: str) -> tuple[Any, int, int] | None:
    if not isinstance(text, str) or not text:
        return None
    for idx, ch in enumerate(text):
        if ch not in "{[":
            continue
        end = _scan_json_document_end(text, idx)
        if end is None:
            continue
        candidate = text[idx:end]
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        byte_from = len(text[:idx].encode("utf-8"))
        byte_to = byte_from + len(candidate.encode("utf-8"))
        return payload, byte_from, byte_to
    return None
