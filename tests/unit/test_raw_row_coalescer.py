from __future__ import annotations

from server.runtime.protocol.raw_row_coalescer import coalesce_raw_rows


def _rows(lines: list[str], *, stream: str = "stderr") -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    cursor = 0
    for line in lines:
        encoded = line.encode("utf-8")
        start = cursor
        cursor += len(encoded)
        rows.append(
            {
                "stream": stream,
                "line": line,
                "byte_from": start,
                "byte_to": cursor,
            }
        )
    return rows


def test_coalesce_raw_rows_merges_embedded_prefixed_json_block() -> None:
    source = _rows(
        [
            "Attempt 1 failed ... GaxiosError: [{",
            '  "error": {"code": 429, "message": "No capacity"}',
            "}]",
        ]
    )
    output, stats = coalesce_raw_rows(source, min_rows=1, max_lines=128, max_chars=32768)
    assert len(output) == 1
    assert "GaxiosError: [{" in output[0]["line"]
    assert '"code": 429' in output[0]["line"]
    assert stats["structured_blocks"] >= 1


def test_coalesce_raw_rows_does_not_break_on_brackets_inside_json_string() -> None:
    source = _rows(
        [
            "warning: payload dump = {",
            '  "message": "contains [array] and {object} markers",',
            '  "status": "RESOURCE_EXHAUSTED"',
            "}",
        ]
    )
    output, stats = coalesce_raw_rows(source, min_rows=1, max_lines=128, max_chars=32768)
    assert len(output) == 1
    assert "contains [array] and {object} markers" in output[0]["line"]
    assert stats["structured_blocks"] >= 1


def test_coalesce_raw_rows_merges_stack_frames_under_error_context() -> None:
    lines = [
        "Attempt 1 failed with status 429. Retrying with backoff... GaxiosError: [{",
        '  "error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}',
        "}]",
    ]
    lines.extend([f"    at async function_{index} (/path/file.js:{100 + index}:20)" for index in range(30)])
    source = _rows(lines)
    output, stats = coalesce_raw_rows(source, min_rows=200, max_lines=128, max_chars=32768)
    assert len(output) == 1
    assert "function_0" in output[0]["line"]
    assert "function_29" in output[0]["line"]
    assert stats["coalesced"] < stats["original"]
    assert stats["error_context_blocks"] >= 1


def test_coalesce_raw_rows_splits_when_error_context_starts_after_warning() -> None:
    source = _rows(
        [
            "Warning: --allowed-tools cli argument is deprecated",
            "GaxiosError: [{",
            '  "error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}',
            "}]",
            "    at async sendRequest (/path/file.js:123:45)",
        ]
    )

    output, _stats = coalesce_raw_rows(source, min_rows=1, max_lines=128, max_chars=32768)
    assert len(output) == 2
    assert output[0]["line"].startswith("Warning:")
    assert output[1]["line"].startswith("GaxiosError:")
    assert "RESOURCE_EXHAUSTED" in output[1]["line"]
