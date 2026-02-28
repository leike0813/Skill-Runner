from __future__ import annotations

import re
from typing import TYPE_CHECKING

from server.runtime.adapter.types import RuntimeAssistantMessage, RuntimeStreamParseResult, RuntimeStreamRawRow
from server.services.runtime_parse_utils import (
    dedup_assistant_messages,
    find_session_id_in_text,
    stream_lines_with_offsets,
    strip_runtime_script_envelope,
)

if TYPE_CHECKING:
    from .execution_adapter import IFlowExecutionAdapter


class IFlowStreamParser:
    def __init__(self, adapter: "IFlowExecutionAdapter") -> None:
        self._adapter = adapter

    def _extract_latest_round_text(self, text: str) -> str:
        if not text.strip():
            return ""
        # iFlow may append multiple rounds with repeated <Execution Info> blocks.
        # Keep only the latest content segment before/after the last execution block.
        segments = re.split(r"<Execution Info>[\s\S]*?</Execution Info>", text)
        for segment in reversed(segments):
            cleaned = segment.strip()
            if not cleaned:
                continue
            cleaned = re.sub(r"(?m)^\s*(?:\S+\s+)?Resuming session.*$", "", cleaned).strip()
            if cleaned:
                return cleaned
        return ""

    def parse(self, raw_stdout: str) -> dict[str, object]:
        result, repair_level = self._adapter._parse_json_with_deterministic_repair(raw_stdout)  # noqa: SLF001
        if result is not None:
            turn_result = self._adapter._build_turn_result_from_payload(result, repair_level)  # noqa: SLF001
            structured_payload = self._adapter._materialize_output_payload(turn_result)  # noqa: SLF001
            return {"turn_result": turn_result.model_dump(), "structured_payload": structured_payload}
        turn_result = self._adapter._turn_error(message="failed to parse iflow output")  # noqa: SLF001
        return {"turn_result": turn_result.model_dump(), "structured_payload": None}

    def parse_runtime_stream(
        self,
        *,
        stdout_raw: bytes,
        stderr_raw: bytes,
        pty_raw: bytes = b"",
    ) -> RuntimeStreamParseResult:
        stdout_rows = strip_runtime_script_envelope(stream_lines_with_offsets("stdout", stdout_raw))
        stderr_rows = strip_runtime_script_envelope(stream_lines_with_offsets("stderr", stderr_raw))
        pty_rows = strip_runtime_script_envelope(stream_lines_with_offsets("pty", pty_raw))
        diagnostics: list[str] = []
        split_merged = "\n".join([row["line"] for row in [*stdout_rows, *stderr_rows] if row["line"]])
        pty_merged = "\n".join([row["line"] for row in pty_rows if row["line"]])
        merged = "\n".join([row["line"] for row in [*stdout_rows, *stderr_rows, *pty_rows] if row["line"]])
        cleaned_split = self._extract_latest_round_text(split_merged)
        cleaned_pty = self._extract_latest_round_text(pty_merged)
        use_pty_fallback = (not cleaned_split) and bool(cleaned_pty)
        cleaned = cleaned_pty if use_pty_fallback else cleaned_split
        assistant_messages: list[RuntimeAssistantMessage] = []
        raw_rows: list[RuntimeStreamRawRow] = []
        confidence = 0.45

        if cleaned:
            assistant_messages.append({"text": cleaned, "raw_ref": None})
            confidence = 0.65
            if use_pty_fallback:
                diagnostics.append("PTY_FALLBACK_USED")
        else:
            raw_rows.extend(stdout_rows)
            raw_rows.extend(stderr_rows)
            raw_rows.extend(pty_rows)
            diagnostics.append("LOW_CONFIDENCE_PARSE")

        if stdout_rows and stderr_rows:
            diagnostics.append("IFLOW_CHANNEL_DRIFT_OBSERVED")

        return {
            "parser": "iflow_text",
            "confidence": confidence,
            "session_id": find_session_id_in_text(merged),
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "raw_rows": raw_rows,
            "diagnostics": list(dict.fromkeys(diagnostics)),
            "structured_types": ["iflow.execution_info"],
        }
