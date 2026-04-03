from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from server.runtime.adapter.common.live_stream_parser_common import NdjsonLiveStreamParserSession
from server.runtime.adapter.common.parser_auth_signal_matcher import (
    detect_auth_signal_from_patterns,
)
from server.runtime.adapter.types import (
    LiveParserEmission,
    RuntimeAssistantMessage,
    RuntimeProcessEvent,
    RuntimeStreamRawRef,
    RuntimeStreamParseResult,
    RuntimeTurnMarker,
)
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

    def _is_turn_start(self, payload: dict[str, Any]) -> bool:
        payload_type = payload.get("type")
        return payload_type in {"step_start", "step.started"}

    def _is_turn_complete(self, payload: dict[str, Any]) -> bool:
        payload_type = payload.get("type")
        return payload_type in {"step_finish", "step.completed"}

    def _extract_turn_complete_data(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self._is_turn_complete(payload):
            return None
        part = payload.get("part")
        if not isinstance(part, dict):
            return None
        data: dict[str, Any] = {}
        if "cost" in part and part.get("cost") is not None:
            data["cost"] = part.get("cost")
        tokens_obj = part.get("tokens")
        if isinstance(tokens_obj, dict):
            data["tokens"] = tokens_obj
        return data or None

    def _extract_process_event(
        self,
        *,
        payload: dict[str, Any],
        row: dict[str, Any],
    ) -> RuntimeProcessEvent | None:
        if payload.get("type") != "tool_use":
            return None
        part = payload.get("part")
        if not isinstance(part, dict) or part.get("type") != "tool":
            return None
        tool_obj = part.get("tool")
        if not isinstance(tool_obj, str) or not tool_obj.strip():
            return None
        tool = tool_obj.strip()
        if tool in {"bash", "grep"}:
            process_type: str = "command_execution"
        elif tool == "apply_patch":
            process_type = "tool_call"
        else:
            process_type = "tool_call"

        state = part.get("state")
        details: dict[str, Any] = {
            "payload_type": payload.get("type"),
            "item_type": "tool_use",
            "tool": tool,
        }
        if isinstance(state, dict):
            status = state.get("status")
            if status is not None:
                details["status"] = status
            input_obj = state.get("input")
            if input_obj is not None:
                details["input"] = input_obj

        summary = f"{tool} completed"
        text_value: str | None = None
        if isinstance(state, dict):
            if process_type == "command_execution":
                input_obj = state.get("input")
                if isinstance(input_obj, dict):
                    command_obj = input_obj.get("command")
                    if isinstance(command_obj, str) and command_obj.strip():
                        summary = command_obj.strip()
                output_obj = state.get("output")
                if isinstance(output_obj, str) and output_obj.strip():
                    text_value = output_obj
            else:
                summary = tool
                input_obj = state.get("input")
                if input_obj is not None:
                    if isinstance(input_obj, str):
                        text_value = input_obj
                    else:
                        text_value = json.dumps(input_obj, ensure_ascii=False)

        part_id = part.get("id")
        if isinstance(part_id, str) and part_id.strip():
            message_id = part_id
        else:
            byte_from = row.get("byte_from")
            message_id = f"{tool}_{byte_from if isinstance(byte_from, int) else 0}"
        raw_ref = {
            "stream": row.get("stream"),
            "byte_from": row.get("byte_from"),
            "byte_to": row.get("byte_to"),
        }
        process_event: RuntimeProcessEvent = {
            "process_type": process_type,  # type: ignore[typeddict-item]
            "message_id": message_id,
            "summary": summary,
            "classification": process_type,
            "details": details,
            "raw_ref": raw_ref,  # type: ignore[typeddict-item]
        }
        if isinstance(text_value, str) and text_value.strip():
            process_event["text"] = text_value
        return process_event

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
        all_records, raw_rows = collect_json_parse_errors(stdout_rows)
        all_pty_records, pty_raw_rows = collect_json_parse_errors(pty_rows)
        records = self._slice_latest_step_rows(all_records)
        pty_records = self._slice_latest_step_rows(all_pty_records)
        assistant_messages: list[RuntimeAssistantMessage] = []
        process_events: list[RuntimeProcessEvent] = []
        diagnostics: list[str] = []
        session_id: str | None = None
        structured_types: list[str] = []
        turn_start_seen = False
        turn_completed = False
        turn_complete_data: dict[str, Any] | None = None
        turn_start_raw_ref: RuntimeStreamRawRef | None = None
        turn_complete_raw_ref: RuntimeStreamRawRef | None = None
        run_handle_id: str | None = None
        run_handle_raw_ref: RuntimeStreamRawRef | None = None
        extracted: dict[str, Any] = {
            "error_name": None,
            "status_code": None,
            "message": None,
            "provider_id": None,
            "response_error_type": None,
            "step_finish_unknown_count": 0,
            "saw_manual_interrupt": False,
        }

        def _accumulate_extracted(parsed_rows: list[dict[str, Any]]) -> None:
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
                if payload_type == "error":
                    error = payload.get("error")
                    if isinstance(error, dict):
                        extracted["error_name"] = error.get("name")
                        data = error.get("data")
                        if isinstance(data, dict):
                            extracted["status_code"] = data.get("statusCode")
                            extracted["message"] = data.get("message")
                            extracted["provider_id"] = data.get("providerID")
                            response_body = data.get("responseBody")
                            if isinstance(response_body, str):
                                try:
                                    response_payload = json.loads(response_body)
                                except json.JSONDecodeError:
                                    response_payload = None
                                if isinstance(response_payload, dict):
                                    error_payload = response_payload.get("error")
                                    if isinstance(error_payload, dict):
                                        extracted["response_error_type"] = error_payload.get("type")
                elif payload_type == "step_finish":
                    part = payload.get("part")
                    if isinstance(part, dict) and part.get("reason") == "unknown":
                        extracted["step_finish_unknown_count"] = int(
                            extracted["step_finish_unknown_count"]
                        ) + 1

        def _consume(parsed_rows: list[dict[str, Any]]) -> None:
            nonlocal session_id, turn_start_seen, turn_completed, turn_complete_data, turn_start_raw_ref, turn_complete_raw_ref
            nonlocal run_handle_id, run_handle_raw_ref
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
                if self._is_turn_start(payload) and not turn_start_seen:
                    turn_start_seen = True
                    turn_start_raw_ref = {
                        "stream": str(row["stream"]),
                        "byte_from": int(row["byte_from"]),
                        "byte_to": int(row["byte_to"]),
                    }
                if (
                    self._is_turn_start(payload)
                    and run_handle_id is None
                    and isinstance(row_session_id, str)
                    and row_session_id.strip()
                ):
                    run_handle_id = row_session_id.strip()
                    run_handle_raw_ref = {
                        "stream": str(row["stream"]),
                        "byte_from": int(row["byte_from"]),
                        "byte_to": int(row["byte_to"]),
                    }
                if self._is_turn_complete(payload):
                    turn_completed = True
                    turn_complete_raw_ref = {
                        "stream": str(row["stream"]),
                        "byte_from": int(row["byte_from"]),
                        "byte_to": int(row["byte_to"]),
                    }
                    extracted_turn_data = self._extract_turn_complete_data(payload)
                    if isinstance(extracted_turn_data, dict):
                        turn_complete_data = extracted_turn_data
                process_event = self._extract_process_event(payload=payload, row=row)
                if process_event is not None:
                    process_events.append(process_event)
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

        _accumulate_extracted(all_records)
        _accumulate_extracted(all_pty_records)
        _consume(records)
        if not assistant_messages and pty_records:
            diagnostics.append("PTY_FALLBACK_USED")
            _consume(pty_records)
        raw_rows.extend(pty_raw_rows)
        if raw_rows:
            diagnostics.append("UNPARSED_CONTENT_FELL_BACK_TO_RAW")
        stdout_text = stdout_raw.decode("utf-8", errors="replace")
        stderr_text = stderr_raw.decode("utf-8", errors="replace")
        pty_text = pty_raw.decode("utf-8", errors="replace")
        combined_text = "\n".join(part for part in (stdout_text, stderr_text, pty_text) if part)
        if extracted.get("provider_id") is None:
            model_match = re.search(r"--model=([a-zA-Z0-9._-]+)/", combined_text)
            if model_match is not None:
                extracted["provider_id"] = model_match.group(1)
        if "^C" in combined_text or 'COMMAND_EXIT_CODE="130"' in combined_text:
            extracted["saw_manual_interrupt"] = True
        auth_signal = detect_auth_signal_from_patterns(
            engine="opencode",
            rules=self._adapter.profile.parser_auth_patterns.rules,
            evidence={
                "engine": "opencode",
                "stdout_text": stdout_text,
                "stderr_text": stderr_text,
                "pty_output": pty_text,
                "combined_text": combined_text,
                "parser_diagnostics": list(dict.fromkeys(diagnostics)),
                "structured_types": list(dict.fromkeys(structured_types)),
                "provider_id": extracted.get("provider_id"),
                "extracted": extracted,
            },
        )
        turn_markers: list[RuntimeTurnMarker] = []
        if turn_start_seen:
            turn_markers.append({"marker": "start", "raw_ref": turn_start_raw_ref})
        if turn_completed:
            marker_payload: RuntimeTurnMarker = {"marker": "complete", "raw_ref": turn_complete_raw_ref}
            if isinstance(turn_complete_data, dict):
                marker_payload["data"] = turn_complete_data
            turn_markers.append(marker_payload)

        result: RuntimeStreamParseResult = {
            "parser": "opencode_ndjson",
            "confidence": 0.95 if assistant_messages else 0.6,
            "session_id": session_id,
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "process_events": process_events,
            "turn_started": turn_start_seen,
            "turn_completed": turn_completed,
            "turn_markers": turn_markers,
            "raw_rows": raw_rows,
            "diagnostics": diagnostics,
            "structured_types": list(dict.fromkeys(structured_types)),
        }
        if isinstance(turn_complete_data, dict):
            result["turn_complete_data"] = turn_complete_data
        if isinstance(run_handle_id, str) and run_handle_id.strip():
            result["run_handle"] = {
                "handle_id": run_handle_id.strip(),
                "raw_ref": run_handle_raw_ref,
            }
        if auth_signal is not None:
            result["auth_signal"] = auth_signal
        return result

    def start_live_session(self) -> "_OpencodeLiveSession":
        return _OpencodeLiveSession(self)


class _OpencodeLiveSession(NdjsonLiveStreamParserSession):
    def __init__(self, parser: OpencodeStreamParser) -> None:
        super().__init__(accepted_streams={"stdout", "pty"})
        self._parser = parser
        self._last_text: str | None = None
        self._turn_start_emitted = False
        self._turn_complete_emitted = False
        self._run_handle_emitted = False

    def handle_live_row(
        self,
        *,
        payload: dict[str, Any],
        raw_ref: RuntimeStreamRawRef,
        stream: str,
    ) -> list[LiveParserEmission]:
        emissions: list[LiveParserEmission] = []
        if self._parser._is_turn_start(payload) and not self._turn_start_emitted:  # noqa: SLF001
            self._turn_start_emitted = True
            emissions.append({"kind": "turn_marker", "marker": "start", "raw_ref": raw_ref})
        session_id = find_session_id(payload)
        if (
            self._parser._is_turn_start(payload)  # noqa: SLF001
            and not self._run_handle_emitted
            and isinstance(session_id, str)
            and session_id.strip()
        ):
            self._run_handle_emitted = True
            emissions.append(
                {
                    "kind": "run_handle",
                    "handle_id": session_id.strip(),
                    "raw_ref": raw_ref,
                }
            )
        if self._parser._is_turn_complete(payload) and not self._turn_complete_emitted:  # noqa: SLF001
            self._turn_complete_emitted = True
            turn_complete_data = self._parser._extract_turn_complete_data(payload)  # noqa: SLF001
            marker_emission: LiveParserEmission = {
                "kind": "turn_marker",
                "marker": "complete",
                "raw_ref": raw_ref,
            }
            if isinstance(turn_complete_data, dict):
                marker_emission["turn_complete_data"] = turn_complete_data
            emissions.append(marker_emission)
            completion_emission: LiveParserEmission = {"kind": "turn_completed"}
            if isinstance(turn_complete_data, dict):
                completion_emission["turn_complete_data"] = turn_complete_data
            emissions.append(completion_emission)
        row_for_process: dict[str, Any] = {
            "stream": stream,
            "byte_from": raw_ref["byte_from"],
            "byte_to": raw_ref["byte_to"],
        }
        process_event = self._parser._extract_process_event(payload=payload, row=row_for_process)  # noqa: SLF001
        if process_event is not None:
            process_emission: LiveParserEmission = {
                "kind": "process_event",
                "process_type": process_event["process_type"],
                "summary": process_event["summary"],
                "classification": process_event.get("classification", process_event["process_type"]),
                "details": process_event.get("details", {}),
                "raw_ref": raw_ref,
            }
            message_id_obj = process_event.get("message_id")
            if isinstance(message_id_obj, str) and message_id_obj.strip():
                process_emission["message_id"] = message_id_obj
            text_obj = process_event.get("text")
            if isinstance(text_obj, str) and text_obj.strip():
                process_emission["text"] = text_obj
            emissions.append(process_emission)
        extracted = self._parser._extract_text_event(payload)  # noqa: SLF001
        if not isinstance(extracted, str) or not extracted.strip() or extracted == self._last_text:
            return emissions
        self._last_text = extracted
        emission: LiveParserEmission = {
            "kind": "assistant_message",
            "text": extracted,
            "raw_ref": raw_ref,
        }
        if session_id:
            emission["session_id"] = session_id
        emissions.append(emission)
        return emissions
