from __future__ import annotations

import json
from typing import TYPE_CHECKING

from server.runtime.adapter.types import LiveParserEmission, RuntimeAssistantMessage
from server.runtime.adapter.common.parser_auth_signal_matcher import (
    detect_auth_signal_from_patterns,
)
from server.runtime.protocol.parse_utils import (
    collect_json_parse_errors,
    dedup_assistant_messages,
    find_session_id,
    stream_lines_with_offsets,
    strip_runtime_script_envelope,
)
if TYPE_CHECKING:
    from .execution_adapter import CodexExecutionAdapter


class CodexStreamParser:
    def __init__(self, adapter: "CodexExecutionAdapter") -> None:
        self._adapter = adapter

    def _slice_latest_turn_rows(self, rows: list[dict[str, object]]) -> list[dict[str, object]]:
        if not rows:
            return rows

        start_idx: int | None = None
        end_idx: int | None = None
        for idx, row in enumerate(rows):
            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue
            event_type = payload.get("type")
            if event_type == "turn.started":
                start_idx = idx
            elif event_type == "turn.completed" and start_idx is not None:
                end_idx = idx

        if start_idx is None:
            return rows
        if end_idx is not None and end_idx >= start_idx:
            return rows[start_idx : end_idx + 1]
        return rows[start_idx:]

    def parse(self, raw_stdout: str) -> dict[str, object]:
        parsed_rows: list[dict[str, object]] = []
        for line in raw_stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                parsed_rows.append({"payload": event})

        last_message_text = ""
        for row in self._slice_latest_turn_rows(parsed_rows):
            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue
            if payload.get("type") != "item.completed":
                continue
            item = payload.get("item")
            if not isinstance(item, dict) or item.get("type") != "agent_message":
                continue
            text = item.get("text")
            if isinstance(text, str):
                last_message_text = text

        if not last_message_text:
            last_message_text = raw_stdout

        result, repair_level = self._adapter._parse_json_with_deterministic_repair(last_message_text)  # noqa: SLF001
        if result is not None:
            turn_result = self._adapter._build_turn_result_from_payload(result, repair_level)  # noqa: SLF001
            structured_payload = self._adapter._materialize_output_payload(turn_result)  # noqa: SLF001
            return {
                "turn_result": turn_result.model_dump(),
                "structured_payload": structured_payload,
            }
        turn_result = self._adapter._turn_error(message="failed to parse codex output")  # noqa: SLF001
        return {
            "turn_result": turn_result.model_dump(),
            "structured_payload": None,
        }

    def parse_runtime_stream(
        self,
        *,
        stdout_raw: bytes,
        stderr_raw: bytes,
        pty_raw: bytes = b"",
    ) -> dict[str, object]:
        stdout_rows = strip_runtime_script_envelope(stream_lines_with_offsets("stdout", stdout_raw))
        pty_rows = strip_runtime_script_envelope(stream_lines_with_offsets("pty", pty_raw))
        records, raw_rows = collect_json_parse_errors(stdout_rows)
        pty_records, pty_raw_rows = collect_json_parse_errors(pty_rows)
        records = self._slice_latest_turn_rows(records)
        pty_records = self._slice_latest_turn_rows(pty_records)

        assistant_messages: list[RuntimeAssistantMessage] = []
        diagnostics: list[str] = []
        session_id: str | None = None
        structured_types: list[str] = []

        for row in records:
            payload = row["payload"]
            if not isinstance(payload, dict):
                continue
            row_session_id = find_session_id(payload)
            if row_session_id and not session_id:
                session_id = row_session_id
            payload_type = payload.get("type")
            if isinstance(payload_type, str):
                structured_types.append(payload_type)
            if payload.get("type") != "item.completed":
                continue
            item = payload.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    row_stream = str(row["stream"])
                    row_from = row["byte_from"]
                    row_to = row["byte_to"]
                    assistant_messages.append(
                        {
                            "text": text,
                            "raw_ref": {
                                "stream": row_stream,
                                "byte_from": row_from if isinstance(row_from, int) else 0,
                                "byte_to": row_to if isinstance(row_to, int) else 0,
                            },
                        }
                    )

        stdout_turn_completed = any(
            isinstance(row["payload"], dict) and row["payload"].get("type") == "turn.completed"
            for row in records
        )
        pty_turn_completed = any(
            isinstance(row["payload"], dict) and row["payload"].get("type") == "turn.completed"
            for row in pty_records
        )
        use_pty_fallback = (not assistant_messages and pty_records) or (
            not stdout_turn_completed and pty_turn_completed
        )

        if use_pty_fallback:
            diagnostics.append("PTY_FALLBACK_USED")
            for row in pty_records:
                payload = row["payload"]
                if not isinstance(payload, dict):
                    continue
                row_session_id = find_session_id(payload)
                if row_session_id and not session_id:
                    session_id = row_session_id
                payload_type = payload.get("type")
                if isinstance(payload_type, str):
                    structured_types.append(payload_type)
                if payload.get("type") != "item.completed":
                    continue
                item = payload.get("item")
                if isinstance(item, dict) and item.get("type") == "agent_message":
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        row_stream = str(row["stream"])
                        row_from = row["byte_from"]
                        row_to = row["byte_to"]
                        assistant_messages.append(
                            {
                                "text": text,
                                "raw_ref": {
                                    "stream": row_stream,
                                    "byte_from": row_from if isinstance(row_from, int) else 0,
                                    "byte_to": row_to if isinstance(row_to, int) else 0,
                                },
                            }
                        )

        raw_rows.extend(pty_raw_rows)
        if raw_rows:
            diagnostics.append("UNPARSED_CONTENT_FELL_BACK_TO_RAW")

        stdout_text = stdout_raw.decode("utf-8", errors="replace")
        stderr_text = stderr_raw.decode("utf-8", errors="replace")
        pty_text = pty_raw.decode("utf-8", errors="replace")
        auth_signal = detect_auth_signal_from_patterns(
            engine="codex",
            rules=self._adapter.profile.parser_auth_patterns.rules,
            evidence={
                "engine": "codex",
                "stdout_text": stdout_text,
                "stderr_text": stderr_text,
                "pty_output": pty_text,
                "combined_text": "\n".join(
                    part for part in (stdout_text, stderr_text, pty_text) if part
                ),
                "parser_diagnostics": list(dict.fromkeys(diagnostics)),
                "structured_types": list(dict.fromkeys(structured_types)),
                "extracted": {},
            },
        )

        result: dict[str, object] = {
            "parser": "codex_ndjson",
            "confidence": 0.95 if assistant_messages else 0.6,
            "session_id": session_id,
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "raw_rows": list(raw_rows),
            "diagnostics": diagnostics,
            "structured_types": list(dict.fromkeys(structured_types)),
        }
        if auth_signal is not None:
            result["auth_signal"] = auth_signal
        return result

    def start_live_session(self) -> "_CodexLiveSession":
        return _CodexLiveSession(self)


class _CodexLiveSession:
    def __init__(self, parser: CodexStreamParser) -> None:
        self._parser = parser
        self._buffers: dict[str, str] = {"stdout": "", "pty": ""}

    def feed(
        self,
        *,
        stream: str,
        text: str,
        byte_from: int,
        byte_to: int,
    ) -> list[LiveParserEmission]:
        if stream not in {"stdout", "pty"}:
            return []
        combined = f"{self._buffers.get(stream, '')}{text}"
        if "\n" not in combined:
            self._buffers[stream] = combined
            return []
        lines = combined.splitlines(keepends=True)
        complete = lines[:-1]
        tail = lines[-1]
        if tail.endswith("\n"):
            complete.append(tail)
            tail = ""
        self._buffers[stream] = tail
        emissions: list[LiveParserEmission] = []
        cursor = max(0, int(byte_to) - len(text.encode("utf-8", errors="replace")))
        for line in complete:
            clean = line.strip()
            encoded = line.encode("utf-8", errors="replace")
            row_from = cursor
            row_to = cursor + len(encoded)
            cursor = row_to
            if not clean:
                continue
            try:
                payload = json.loads(clean)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("type") != "item.completed":
                continue
            item = payload.get("item")
            if not isinstance(item, dict) or item.get("type") != "agent_message":
                continue
            text_obj = item.get("text")
            if not isinstance(text_obj, str) or not text_obj.strip():
                continue
            emission: LiveParserEmission = {
                "kind": "assistant_message",
                "text": text_obj,
                "raw_ref": {
                    "stream": stream,
                    "byte_from": row_from,
                    "byte_to": row_to,
                },
            }
            session_id = find_session_id(payload)
            if session_id:
                emission["session_id"] = session_id
            emissions.append(emission)
        return emissions

    def finish(
        self,
        *,
        exit_code: int,
        failure_reason: str | None,
    ) -> list[LiveParserEmission]:
        _ = exit_code
        _ = failure_reason
        return []
