from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from server.runtime.adapter.types import RuntimeAssistantMessage, RuntimeStreamParseResult
from server.runtime.protocol.parse_utils import (
    collect_json_parse_errors,
    dedup_assistant_messages,
    find_session_id,
    stream_lines_with_offsets,
    strip_runtime_script_envelope,
)

if TYPE_CHECKING:
    from .execution_adapter import OpencodeExecutionAdapter


class OpencodeStreamParser:
    def __init__(self, adapter: "OpencodeExecutionAdapter") -> None:
        self._adapter = adapter

    def _slice_latest_step_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return rows

        step_start_types = {"step_start", "step.started"}
        step_finish_types = {"step_finish", "step.completed"}
        start_idx: int | None = None
        end_idx: int | None = None

        for idx, row in enumerate(rows):
            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue
            payload_type = payload.get("type")
            if payload_type in step_start_types:
                start_idx = idx
            elif payload_type in step_finish_types and start_idx is not None:
                end_idx = idx

        if start_idx is None:
            return rows
        if end_idx is not None and end_idx >= start_idx:
            return rows[start_idx : end_idx + 1]
        return rows[start_idx:]

    def _extract_text_event(self, payload: dict[str, Any]) -> str | None:
        payload_type = payload.get("type")
        if payload_type != "text":
            return None
        part = payload.get("part")
        if isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                return text
        text = payload.get("text")
        if isinstance(text, str) and text.strip():
            return text
        return None

    def parse(self, raw_stdout: str) -> dict[str, object]:
        parsed_rows: list[dict[str, Any]] = []
        for line in raw_stdout.splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            parsed_rows.append({"payload": payload})

        last_text = ""
        for row in self._slice_latest_step_rows(parsed_rows):
            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue
            extracted = self._extract_text_event(payload)
            if extracted:
                last_text = extracted
        source_text = last_text or raw_stdout
        result, repair_level = self._adapter._parse_json_with_deterministic_repair(source_text)  # noqa: SLF001
        if result is not None:
            turn_result = self._adapter._build_turn_result_from_payload(result, repair_level)  # noqa: SLF001
            structured_payload = self._adapter._materialize_output_payload(turn_result)  # noqa: SLF001
            return {"turn_result": turn_result.model_dump(), "structured_payload": structured_payload}
        turn_result = self._adapter._turn_error(message="failed to parse opencode output")  # noqa: SLF001
        return {"turn_result": turn_result.model_dump(), "structured_payload": None}

    def parse_runtime_stream(
        self,
        *,
        stdout_raw: bytes,
        stderr_raw: bytes,
        pty_raw: bytes = b"",
    ) -> RuntimeStreamParseResult:
        stdout_rows = strip_runtime_script_envelope(stream_lines_with_offsets("stdout", stdout_raw))
        pty_rows = strip_runtime_script_envelope(stream_lines_with_offsets("pty", pty_raw))
        records, raw_rows = collect_json_parse_errors(stdout_rows)
        pty_records, pty_raw_rows = collect_json_parse_errors(pty_rows)
        records = self._slice_latest_step_rows(records)
        pty_records = self._slice_latest_step_rows(pty_records)
        assistant_messages: list[RuntimeAssistantMessage] = []
        diagnostics: list[str] = []
        session_id: str | None = None
        structured_types: list[str] = []

        def _consume(parsed_rows: list[dict[str, Any]]) -> None:
            nonlocal session_id
            for row in parsed_rows:
                payload = row["payload"]
                row_session_id = find_session_id(payload)
                if row_session_id and not session_id:
                    session_id = row_session_id
                payload_type = payload.get("type")
                if isinstance(payload_type, str):
                    structured_types.append(payload_type)
                if not isinstance(payload, dict):
                    continue
                text = self._extract_text_event(payload)
                if isinstance(text, str) and text.strip():
                    assistant_messages.append(
                        {
                            "text": text,
                            "raw_ref": {
                                "stream": row["stream"],
                                "byte_from": row["byte_from"],
                                "byte_to": row["byte_to"],
                            },
                        }
                    )

        _consume(records)
        if not assistant_messages and pty_records:
            diagnostics.append("PTY_FALLBACK_USED")
            _consume(pty_records)
        raw_rows.extend(pty_raw_rows)
        if raw_rows:
            diagnostics.append("UNPARSED_CONTENT_FELL_BACK_TO_RAW")
        return {
            "parser": "opencode_ndjson",
            "confidence": 0.95 if assistant_messages else 0.6,
            "session_id": session_id,
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "raw_rows": raw_rows,
            "diagnostics": diagnostics,
            "structured_types": list(dict.fromkeys(structured_types)),
        }
