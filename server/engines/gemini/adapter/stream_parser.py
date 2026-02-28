from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from server.runtime.adapter.types import RuntimeAssistantMessage, RuntimeStreamParseResult, RuntimeStreamRawRow
from server.runtime.protocol.parse_utils import (
    collect_json_parse_errors,
    dedup_assistant_messages,
    extract_fenced_or_plain_json,
    extract_json_document_with_span,
    find_session_id,
    find_session_id_in_text,
    stream_lines_with_offsets,
    strip_runtime_script_envelope,
)

if TYPE_CHECKING:
    from .execution_adapter import GeminiExecutionAdapter


class GeminiStreamParser:
    def __init__(self, adapter: "GeminiExecutionAdapter") -> None:
        self._adapter = adapter

    def _extract_last_json_document_with_span(self, text: str) -> tuple[Any, int, int] | None:
        cursor = 0
        last_match: tuple[Any, int, int] | None = None
        while cursor < len(text):
            found = extract_json_document_with_span(text[cursor:])
            if found is None:
                break
            payload, rel_start, rel_end = found
            abs_start = cursor + rel_start
            abs_end = cursor + rel_end
            last_match = (payload, abs_start, abs_end)
            cursor = max(abs_end, cursor + 1)
        return last_match

    def _select_latest_response_records(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not records:
            return []
        latest_index: int | None = None
        for idx, row in enumerate(records):
            payload = row.get("payload")
            if isinstance(payload, dict) and "response" in payload:
                latest_index = idx
        if latest_index is not None:
            return [records[latest_index]]
        return [records[-1]]

    def parse(self, raw_stdout: str) -> dict[str, object]:
        response_text = raw_stdout
        used_envelope_response = False
        envelope: Any | None = None
        try:
            envelope = json.loads(raw_stdout)
        except json.JSONDecodeError:
            envelope = None

        if not isinstance(envelope, dict):
            last_doc = self._extract_last_json_document_with_span(raw_stdout)
            if last_doc is not None:
                candidate_payload = last_doc[0]
                if isinstance(candidate_payload, dict):
                    envelope = candidate_payload

        if isinstance(envelope, dict) and "response" in envelope:
            used_envelope_response = True
            response = envelope["response"]
            if isinstance(response, str):
                response_text = response
            else:
                response_text = json.dumps(response, ensure_ascii=False)

        result, repair_level = self._adapter._parse_json_with_deterministic_repair(response_text)  # noqa: SLF001
        if result is None:
            turn_result = self._adapter._turn_error(message="failed to parse gemini output")  # noqa: SLF001
            return {"turn_result": turn_result.model_dump(), "structured_payload": None}
        if used_envelope_response and repair_level == "none":
            repair_level = "deterministic_generic"
        turn_result = self._adapter._build_turn_result_from_payload(result, repair_level)  # noqa: SLF001
        structured_payload = self._adapter._materialize_output_payload(turn_result)  # noqa: SLF001
        return {"turn_result": turn_result.model_dump(), "structured_payload": structured_payload}

    def parse_runtime_stream(
        self,
        *,
        stdout_raw: bytes,
        stderr_raw: bytes,
        pty_raw: bytes = b"",
    ) -> RuntimeStreamParseResult:
        stdout_rows = strip_runtime_script_envelope(stream_lines_with_offsets("stdout", stdout_raw))
        stderr_rows = stream_lines_with_offsets("stderr", stderr_raw)
        pty_rows = strip_runtime_script_envelope(stream_lines_with_offsets("pty", pty_raw))
        stdout_text = stdout_raw.decode("utf-8", errors="replace")
        stderr_text = stderr_raw.decode("utf-8", errors="replace")
        pty_text = pty_raw.decode("utf-8", errors="replace")

        assistant_messages: list[RuntimeAssistantMessage] = []
        diagnostics: list[str] = []
        session_id: str | None = None
        structured_types: list[str] = []
        confidence = 0.5
        consumed_ranges: dict[str, list[tuple[int, int]]] = {
            "stdout": [],
            "stderr": [],
            "pty": [],
        }

        def _mark_consumed(stream: str, byte_from: int, byte_to: int) -> None:
            if byte_from < 0 or byte_to <= byte_from:
                return
            bucket = consumed_ranges.get(stream)
            if bucket is None:
                return
            bucket.append((byte_from, byte_to))

        def _consume_payload(
            *,
            payload: Any,
            stream: str,
            byte_from: int,
            byte_to: int,
            structured_type: str,
        ) -> bool:
            nonlocal session_id, confidence
            if not isinstance(payload, dict):
                return False
            if structured_type:
                structured_types.append(structured_type)
            consumed = False
            row_session_id = find_session_id(payload)
            if row_session_id and not session_id:
                session_id = row_session_id
            response = payload.get("response")
            if isinstance(response, str) and response.strip():
                assistant_messages.append(
                    {
                        "text": response,
                        "raw_ref": {
                            "stream": stream,
                            "byte_from": byte_from,
                            "byte_to": byte_to,
                        },
                    }
                )
                confidence = max(confidence, 0.9 if stream == "stderr" else 0.8)
                consumed = True
            elif response is not None:
                assistant_messages.append(
                    {
                        "text": json.dumps(response, ensure_ascii=False),
                        "raw_ref": {
                            "stream": stream,
                            "byte_from": byte_from,
                            "byte_to": byte_to,
                        },
                    }
                )
                confidence = max(confidence, 0.8 if stream == "stderr" else 0.75)
                consumed = True
            if row_session_id:
                consumed = True
            if consumed:
                _mark_consumed(stream, byte_from, byte_to)
            return consumed

        def _consume_stream_records(records: list[dict[str, Any]]) -> bool:
            consumed_any = False
            selected_records = self._select_latest_response_records(records)
            for row in selected_records:
                if _consume_payload(
                    payload=row["payload"],
                    stream=str(row["stream"]),
                    byte_from=int(row["byte_from"]),
                    byte_to=int(row["byte_to"]),
                    structured_type="gemini.stream_response",
                ):
                    consumed_any = True
            return consumed_any

        def _document_json_fallback(*, stream: str, text: str, raw_size: int) -> bool:
            doc = self._extract_last_json_document_with_span(text)
            if doc is None:
                return False
            payload, byte_from, byte_to = doc
            return _consume_payload(
                payload=payload,
                stream=stream,
                byte_from=byte_from,
                byte_to=byte_to if byte_to > byte_from else raw_size,
                structured_type="gemini.stream_response" if stream != "stderr" else "gemini.response",
            )

        used_stream_json_fallback = False
        if stderr_text.strip():
            stderr_used = _document_json_fallback(stream="stderr", text=stderr_text, raw_size=len(stderr_raw))
            if not stderr_used:
                fallback = extract_fenced_or_plain_json(stderr_text)
                if fallback is not None:
                    stderr_used = _consume_payload(
                        payload=fallback,
                        stream="stderr",
                        byte_from=0,
                        byte_to=len(stderr_raw),
                        structured_type="gemini.fenced_json_fallback",
                    )
                if not stderr_used:
                    diagnostics.append("GEMINI_STDERR_JSON_PARSE_FAILED")

        if not assistant_messages and stdout_text.strip():
            stdout_used = _document_json_fallback(stream="stdout", text=stdout_text, raw_size=len(stdout_raw))
            if not stdout_used:
                stdout_records, _ = collect_json_parse_errors(stdout_rows)
                stdout_used = _consume_stream_records(stdout_records)
            if stdout_used:
                used_stream_json_fallback = True

        pty_used = False
        if not assistant_messages and pty_text.strip():
            pty_used = _document_json_fallback(stream="pty", text=pty_text, raw_size=len(pty_raw))
            if not pty_used:
                pty_records, _ = collect_json_parse_errors(pty_rows)
                pty_used = _consume_stream_records(pty_records)
            if pty_used:
                diagnostics.append("PTY_FALLBACK_USED")
                used_stream_json_fallback = True

        if used_stream_json_fallback:
            diagnostics.append("GEMINI_STREAM_JSON_FALLBACK_USED")

        if not session_id:
            session_id = (
                find_session_id_in_text(stderr_text)
                or find_session_id_in_text(stdout_text)
                or find_session_id_in_text(pty_text)
            )

        def _row_overlaps_consumed(row: RuntimeStreamRawRow) -> bool:
            ranges = consumed_ranges.get(row["stream"], [])
            if not ranges:
                return False
            row_start = int(row["byte_from"])
            row_end = int(row["byte_to"])
            for start, end in ranges:
                if row_start < end and row_end > start:
                    return True
            return False

        raw_candidates: list[RuntimeStreamRawRow] = [*stdout_rows, *stderr_rows]
        if pty_used:
            raw_candidates.extend(pty_rows)
        raw_rows = [row for row in raw_candidates if not _row_overlaps_consumed(row)]

        if any(row["stream"] == "stdout" for row in raw_rows):
            diagnostics.append("GEMINI_STDOUT_NOISE")

        return {
            "parser": "gemini_json",
            "confidence": confidence,
            "session_id": session_id,
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "raw_rows": raw_rows,
            "diagnostics": list(dict.fromkeys(diagnostics)),
            "structured_types": list(dict.fromkeys(structured_types)),
        }
