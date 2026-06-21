#!/usr/bin/env python3
"""Render chat_replay.jsonl audit rows as a readable Markdown transcript."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_MAX_TEXT_CHARS = 4000


def main() -> int:
    args = parse_args()
    rows, errors = read_jsonl(args.input)
    markdown = render_markdown(
        rows,
        source=args.input,
        errors=errors,
        full=args.full,
        max_text_chars=args.max_text_chars,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0 if not errors else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a Skill Runner chat_replay.jsonl audit file to Markdown.",
    )
    parser.add_argument("input", type=Path, help="Path to chat_replay.jsonl")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output Markdown path. Defaults to stdout.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Do not truncate long text, tool inputs, or tool results.",
    )
    parser.add_argument(
        "--max-text-chars",
        type=int,
        default=DEFAULT_MAX_TEXT_CHARS,
        help=f"Maximum characters per rendered field unless --full is used. Default: {DEFAULT_MAX_TEXT_CHARS}.",
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: invalid JSON: {exc}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"line {line_number}: row is not a JSON object")
            continue
        payload["_line_number"] = line_number
        rows.append(payload)
    return rows, errors


def render_markdown(
    rows: list[dict[str, Any]],
    *,
    source: Path,
    errors: list[str],
    full: bool,
    max_text_chars: int,
) -> str:
    lines: list[str] = []
    lines.append("# Chat Replay")
    lines.append("")
    lines.extend(render_overview(rows, source=source, errors=errors, full=full))
    lines.append("")
    lines.extend(render_stats(rows))
    lines.append("")
    lines.append("## Timeline")
    lines.append("")
    for row in rows:
        lines.extend(render_event(row, full=full, max_text_chars=max_text_chars))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_overview(
    rows: list[dict[str, Any]],
    *,
    source: Path,
    errors: list[str],
    full: bool,
) -> list[str]:
    run_ids = sorted({str(row.get("run_id")) for row in rows if row.get("run_id")})
    attempts = sorted({str(row.get("attempt")) for row in rows if row.get("attempt") is not None})
    seq_values = [row.get("seq") for row in rows if isinstance(row.get("seq"), int)]
    created_values = [str(row.get("created_at")) for row in rows if row.get("created_at")]
    result = [
        "## Overview",
        "",
        f"- Source: `{source}`",
        f"- Rows: `{len(rows)}`",
        f"- Render mode: `{'full' if full else 'truncated'}`",
    ]
    if run_ids:
        result.append(f"- Run ID: `{', '.join(run_ids)}`")
    if attempts:
        result.append(f"- Attempts: `{', '.join(attempts)}`")
    if seq_values:
        result.append(f"- Seq range: `{min(seq_values)}..{max(seq_values)}`")
    if created_values:
        result.append(f"- Time range: `{created_values[0]} -> {created_values[-1]}`")
    if errors:
        result.append(f"- Parse errors: `{len(errors)}`")
        result.append("")
        result.append("### Parse Errors")
        result.append("")
        result.extend(f"- {error}" for error in errors)
    return result


def render_stats(rows: list[dict[str, Any]]) -> list[str]:
    role_counts = Counter(str(row.get("role", "")) for row in rows)
    kind_counts = Counter(str(row.get("kind", "")) for row in rows)
    process_counts = Counter(
        str(correlation(row).get("process_type", "")) for row in rows
    )
    tool_counts = Counter(
        str(details(row).get("tool_name", "")) for row in rows if details(row).get("tool_name")
    )
    item_counts = Counter(
        str(details(row).get("item_type", "")) for row in rows if details(row).get("item_type")
    )
    result = ["## Stats", ""]
    result.extend(render_counter_table("Roles", role_counts))
    result.append("")
    result.extend(render_counter_table("Kinds", kind_counts))
    result.append("")
    result.extend(render_counter_table("Process Types", process_counts))
    result.append("")
    result.extend(render_counter_table("Item Types", item_counts))
    if tool_counts:
        result.append("")
        result.extend(render_counter_table("Tools", tool_counts))
    return result


def render_counter_table(title: str, counts: Counter[str]) -> list[str]:
    result = [f"### {title}", "", "| Value | Count |", "|---|---:|"]
    for value, count in counts.most_common():
        label = value if value else "(empty)"
        result.append(f"| {escape_table(label)} | {count} |")
    return result


def render_event(row: dict[str, Any], *, full: bool, max_text_chars: int) -> list[str]:
    corr = correlation(row)
    det = details(row)
    seq = row.get("seq", "?")
    title = event_title(row)
    meta = [
        f"`line {row.get('_line_number', '?')}`",
        f"`{row.get('created_at', 'unknown time')}`",
        f"`role={row.get('role', '')}`",
        f"`kind={row.get('kind', '')}`",
    ]
    if corr.get("process_type"):
        meta.append(f"`process={corr.get('process_type')}`")
    if det.get("tool_name"):
        meta.append(f"`tool={det.get('tool_name')}`")
    if corr.get("fcmp_seq") is not None:
        meta.append(f"`fcmp_seq={corr.get('fcmp_seq')}`")

    result = [f"### {seq}. {title}", "", " ".join(meta), ""]
    item_type = det.get("item_type")
    if item_type == "tool_use":
        result.extend(render_tool_use(row, full=full, max_text_chars=max_text_chars))
    elif item_type == "tool_result":
        result.extend(render_tool_result(row, full=full, max_text_chars=max_text_chars))
    elif item_type == "thinking":
        result.extend(render_text_section("Reasoning", row.get("text"), full, max_text_chars))
    else:
        result.extend(render_text_section("Text", row.get("text"), full, max_text_chars))

    result.append("")
    result.extend(render_correlation_details(row, full=full, max_text_chars=max_text_chars))
    return result


def event_title(row: dict[str, Any]) -> str:
    det = details(row)
    kind = str(row.get("kind") or "event")
    item_type = str(det.get("item_type") or "")
    tool_name = det.get("tool_name")
    if item_type == "tool_use" and tool_name:
        return f"Tool Use: {tool_name}"
    if item_type == "tool_result" and tool_name:
        status = "error" if det.get("is_error") else "ok"
        return f"Tool Result: {tool_name} ({status})"
    if item_type == "thinking":
        return "Reasoning"
    if kind == "assistant_final":
        return "Assistant Final"
    if kind == "assistant_message":
        return "Assistant Message"
    if kind == "orchestration_notice":
        return "Orchestration Notice"
    return kind.replace("_", " ").title()


def render_tool_use(
    row: dict[str, Any],
    *,
    full: bool,
    max_text_chars: int,
) -> list[str]:
    det = details(row)
    tool_input = det.get("input")
    result: list[str] = []
    if isinstance(tool_input, dict):
        command = tool_input.get("command")
        description = tool_input.get("description")
        file_path = tool_input.get("file_path")
        content = tool_input.get("content")
        if description:
            result.append(f"**Description:** {description}")
            result.append("")
        if command:
            result.append("**Command:**")
            result.append("")
            result.append(code_block(clamp(str(command), full, max_text_chars), "bash"))
        elif file_path:
            result.append(f"**File:** `{file_path}`")
            result.append("")
        if content is not None:
            result.append("**Content:**")
            result.append("")
            result.append(code_block(clamp(as_text(content), full, max_text_chars), guess_lang(content)))
        extra_input = {k: v for k, v in tool_input.items() if k not in {"command", "description", "file_path", "content"}}
        if extra_input:
            result.append("**Input:**")
            result.append("")
            result.append(code_block(clamp(as_json(extra_input), full, max_text_chars), "json"))
    elif tool_input is not None:
        result.extend(render_text_section("Input", tool_input, full, max_text_chars))
    else:
        result.extend(render_text_section("Text", row.get("text"), full, max_text_chars))
    return result


def render_tool_result(
    row: dict[str, Any],
    *,
    full: bool,
    max_text_chars: int,
) -> list[str]:
    det = details(row)
    tool_result = det.get("tool_use_result")
    result: list[str] = []
    if det.get("is_error"):
        result.append("**Status:** error")
        result.append("")
    if isinstance(tool_result, dict):
        stdout = tool_result.get("stdout")
        stderr = tool_result.get("stderr")
        if stdout not in (None, ""):
            result.append("**Stdout:**")
            result.append("")
            result.append(code_block(clamp(str(stdout), full, max_text_chars), "text"))
        if stderr not in (None, ""):
            result.append("**Stderr:**")
            result.append("")
            result.append(code_block(clamp(str(stderr), full, max_text_chars), "text"))
        remainder = {
            k: v
            for k, v in tool_result.items()
            if k not in {"stdout", "stderr"} and v not in (None, "", [], {})
        }
        if remainder:
            result.append("**Result Metadata:**")
            result.append("")
            result.append(code_block(clamp(as_json(remainder), full, max_text_chars), "json"))
    elif tool_result is not None:
        result.extend(render_text_section("Result", tool_result, full, max_text_chars))
    else:
        result.extend(render_text_section("Text", row.get("text"), full, max_text_chars))
    return result


def render_text_section(
    title: str,
    value: Any,
    full: bool,
    max_text_chars: int,
) -> list[str]:
    text = clamp(as_text(value), full, max_text_chars)
    if not text:
        return [f"**{title}:** _(empty)_"]
    return [f"**{title}:**", "", code_block(text, guess_lang(text))]


def render_correlation_details(
    row: dict[str, Any],
    *,
    full: bool,
    max_text_chars: int,
) -> list[str]:
    corr = correlation(row)
    if not corr:
        return []
    slim = {
        key: value
        for key, value in corr.items()
        if key
        not in {
            "details",
        }
    }
    det = details(row)
    if det:
        slim["details_summary"] = {
            key: value
            for key, value in det.items()
            if key not in {"input", "tool_use_result"}
        }
    result = [
        "<details>",
        "<summary>Correlation metadata</summary>",
        "",
        code_block(clamp(as_json(slim), full, max_text_chars), "json"),
        "",
        "</details>",
    ]
    return result


def correlation(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("correlation")
    return value if isinstance(value, dict) else {}


def details(row: dict[str, Any]) -> dict[str, Any]:
    value = correlation(row).get("details")
    return value if isinstance(value, dict) else {}


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return as_json(value)


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def clamp(value: str, full: bool, max_text_chars: int) -> str:
    if full or max_text_chars < 1 or len(value) <= max_text_chars:
        return value
    omitted = len(value) - max_text_chars
    return f"{value[:max_text_chars]}\n\n...[truncated {omitted} characters; rerun with --full]..."


def code_block(value: str, language: str = "") -> str:
    fence = fence_for(value)
    suffix = f"{fence}" if not language else f"{fence}{language}"
    return f"{suffix}\n{value.rstrip()}\n{fence}"


def fence_for(value: str) -> str:
    longest = 0
    current = 0
    for char in value:
        if char == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return "`" * max(3, longest + 1)


def guess_lang(value: Any) -> str:
    text = value if isinstance(value, str) else as_text(value)
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return "json"
    if "\n" not in text and any(token in text for token in ("python ", "pytest", "uv run", "ls ", "cat ")):
        return "bash"
    return "text"


def escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
