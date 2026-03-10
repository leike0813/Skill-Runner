from __future__ import annotations

import json
import re
from typing import Any

from server.runtime.adapter.types import RuntimeStreamRawRow

DEFAULT_RAW_EVENT_COALESCE_MIN_ROWS = 200
DEFAULT_RAW_EVENT_COALESCE_MAX_LINES = 64
DEFAULT_RAW_EVENT_COALESCE_MAX_CHARS = 24576

_RAW_BOUNDARY_PREFIXES = ("Traceback", "Exception", "Error:", "Caused by:")
_RAW_STACK_FRAME_PATTERN = re.compile(r'^\s*(?:File\s+".*?",\s*line\s+\d+|at\s+\S+)')
_ERROR_CONTEXT_START_PATTERN = re.compile(
    r"(?:\b\w*Error\b|\b\w*Exception\b|\bGaxiosError\b|\bstatus\s*[:=]\s*429\b|\bcode\s*[:=]\s*429\b|\bToo Many Requests\b|\bRESOURCE_EXHAUSTED\b|\brateLimitExceeded\b)"
)


def _is_atomic_json_line(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 2:
        return False
    if not ((stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]"))):
        return False
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, (dict, list))


def _find_first_json_structure_start(text: str) -> int | None:
    for index, ch in enumerate(text):
        if ch in "[{":
            return index
    return None


def _find_balanced_structure_end(text: str, start_index: int) -> int | None:
    if start_index < 0 or start_index >= len(text):
        return None
    opener = text[start_index]
    if opener not in "[{":
        return None
    closer = "}" if opener == "{" else "]"

    stack: list[str] = [closer]
    in_string = False
    escaped = False

    for index in range(start_index + 1, len(text)):
        ch = text[index]
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
        if ch in "[{":
            stack.append("}" if ch == "{" else "]")
            continue
        if ch in "}]":
            if not stack or ch != stack[-1]:
                return None
            stack.pop()
            if not stack:
                return index + 1

    return None


def _is_error_context_start(line: str) -> bool:
    return bool(_ERROR_CONTEXT_START_PATTERN.search(line))


def _should_force_coalescing(raw_rows: list[RuntimeStreamRawRow]) -> bool:
    for row in raw_rows:
        line = str(row.get("line") or "")
        if _is_error_context_start(line):
            return True
        if _RAW_STACK_FRAME_PATTERN.match(line):
            return True
    return False


def _should_split_raw_block(line: str, *, in_error_context: bool = False) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if in_error_context:
        return False
    if stripped.startswith(_RAW_BOUNDARY_PREFIXES):
        return True
    if _RAW_STACK_FRAME_PATTERN.match(line):
        return True
    if _is_atomic_json_line(line):
        return True
    return False


def _coalesce_pretty_json_blocks(raw_rows: list[RuntimeStreamRawRow]) -> tuple[list[RuntimeStreamRawRow], int]:
    if not raw_rows:
        return raw_rows, 0

    output: list[RuntimeStreamRawRow] = []
    index = 0
    max_probe_lines = 96
    structured_blocks = 0

    while index < len(raw_rows):
        row = raw_rows[index]
        stream = row["stream"]
        line = row["line"]

        if stream not in {"stdout", "stderr"}:
            output.append(row)
            index += 1
            continue

        if _is_atomic_json_line(line):
            output.append(row)
            index += 1
            continue

        structure_start = _find_first_json_structure_start(line)
        if structure_start is None:
            output.append(row)
            index += 1
            continue

        merged_lines = [line]
        merged_from = row["byte_from"]
        merged_to = row["byte_to"]
        consumed_until: int | None = None

        for probe in range(index + 1, min(len(raw_rows), index + max_probe_lines)):
            next_row = raw_rows[probe]
            if next_row["stream"] != stream:
                break
            merged_lines.append(next_row["line"])
            merged_to = next_row["byte_to"]
            candidate = "\n".join(merged_lines)
            candidate_start = _find_first_json_structure_start(candidate)
            if candidate_start is None:
                continue
            candidate_end = _find_balanced_structure_end(candidate, candidate_start)
            if candidate_end is None:
                continue
            fragment = candidate[candidate_start:candidate_end]
            try:
                payload = json.loads(fragment)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, (dict, list)):
                consumed_until = probe
                break

        if consumed_until is None:
            output.append(row)
            index += 1
            continue

        output.append(
            {
                "stream": stream,
                "line": "\n".join(merged_lines),
                "byte_from": merged_from,
                "byte_to": merged_to,
            }
        )
        structured_blocks += 1
        index = consumed_until + 1

    return output, structured_blocks


def coalesce_raw_rows(
    raw_rows: list[RuntimeStreamRawRow],
    *,
    min_rows: int = DEFAULT_RAW_EVENT_COALESCE_MIN_ROWS,
    max_lines: int = DEFAULT_RAW_EVENT_COALESCE_MAX_LINES,
    max_chars: int = DEFAULT_RAW_EVENT_COALESCE_MAX_CHARS,
) -> tuple[list[RuntimeStreamRawRow], dict[str, int]]:
    original_count = len(raw_rows)
    pre_coalesced, structured_blocks = _coalesce_pretty_json_blocks(raw_rows)
    if len(pre_coalesced) < max(1, int(min_rows)) and not _should_force_coalescing(pre_coalesced):
        return pre_coalesced, {
            "original": original_count,
            "coalesced": len(pre_coalesced),
            "structured_blocks": structured_blocks,
            "error_context_blocks": 0,
        }

    output: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_line_count = 0
    current_char_count = 0
    error_context_blocks = 0

    def _flush_current() -> None:
        nonlocal current, current_line_count, current_char_count, error_context_blocks
        if current is not None:
            if bool(current.get("_error_context")):
                error_context_blocks += 1
            output.append(current)
        current = None
        current_line_count = 0
        current_char_count = 0

    for raw_row in pre_coalesced:
        if not isinstance(raw_row, dict):
            continue
        stream = str(raw_row.get("stream") or "stdout")
        line = str(raw_row.get("line") or "")
        byte_from = max(0, int(raw_row.get("byte_from", 0)))
        byte_to = max(byte_from, int(raw_row.get("byte_to", byte_from)))

        if stream not in {"stdout", "stderr"}:
            _flush_current()
            output.append({"stream": stream, "line": line, "byte_from": byte_from, "byte_to": byte_to})
            continue

        in_error_context = bool(current and current.get("_error_context"))
        split_here = _should_split_raw_block(line, in_error_context=in_error_context)
        atomic_line = _is_atomic_json_line(line)
        row_starts_error_context = _is_error_context_start(line)
        current_is_error_context = bool(current and current.get("_error_context"))
        exceeded = (
            current is not None
            and (
                current_line_count >= max(1, int(max_lines))
                or (current_char_count + len(line)) > max(1, int(max_chars))
            )
        )

        # Preserve visibility of meaningful error chunks in UI summaries:
        # when a new row starts error context, do not keep it merged under a preceding
        # non-error row (e.g. warning/header line).
        if current is not None and row_starts_error_context and not current_is_error_context:
            _flush_current()

        if (
            current is not None
            and (
                current.get("stream") != stream
                or split_here
                or exceeded
                or bool(current.get("_atomic"))
            )
        ):
            _flush_current()

        if current is None:
            current = {
                "stream": stream,
                "line": line,
                "byte_from": byte_from,
                "byte_to": byte_to,
                "_atomic": atomic_line,
                "_error_context": row_starts_error_context,
            }
            current_line_count = 1
            current_char_count = len(line)
            continue

        current["line"] = f"{current.get('line', '')}\n{line}"
        current["byte_to"] = byte_to
        current["_atomic"] = False
        current["_error_context"] = bool(current.get("_error_context")) or row_starts_error_context
        current_line_count += 1
        current_char_count += len(line)

    _flush_current()
    typed_output: list[RuntimeStreamRawRow] = []
    for row in output:
        row.pop("_atomic", None)
        row.pop("_error_context", None)
        typed_output.append(
            {
                "stream": str(row.get("stream") or "stdout"),
                "line": str(row.get("line") or ""),
                "byte_from": max(0, int(row.get("byte_from", 0))),
                "byte_to": max(0, int(row.get("byte_to", 0))),
            }
        )
    return typed_output, {
        "original": original_count,
        "coalesced": len(typed_output),
        "structured_blocks": structured_blocks,
        "error_context_blocks": error_context_blocks,
    }
