from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from typing import Any

from server.runtime.adapter.common.live_stream_parser_common import (
    NdjsonLiveStreamParserSession,
    SemanticOverflowExemptionKind,
    parse_repaired_ndjson_dict,
)
from server.runtime.adapter.common.parser_auth_signal_matcher import (
    detect_auth_signal_from_patterns,
)
from server.runtime.adapter.types import (
    LiveParserEmission,
    RuntimeAssistantMessage,
    RuntimeProcessEvent,
    RuntimeStreamParseResult,
    RuntimeStreamRawRef,
    RuntimeTurnMarker,
)
from server.runtime.protocol.parse_utils import (
    collect_json_parse_errors,
    dedup_assistant_messages,
    find_session_id,
    stream_lines_with_offsets,
    strip_runtime_script_envelope,
)

ErrorExtractor = Callable[[dict[str, Any]], dict[str, Any] | None]


class OpenCodeFamilyStreamParserCore:
    """Shared parser for OpenCode-family JSONL streams."""

    def __init__(
        self,
        *,
        engine: str,
        parser_name: str,
        auth_rules: Sequence[Any],
        error_extractor: ErrorExtractor | None = None,
        fixed_provider_id: str | None = None,
        mark_error_rows_failed: bool = False,
    ) -> None:
        self.engine = engine
        self.parser_name = parser_name
        self.auth_rules = auth_rules
        self.error_extractor = error_extractor
        self.fixed_provider_id = fixed_provider_id
        self.mark_error_rows_failed = mark_error_rows_failed

    def classify_ndjson_overflow_exemption(
        self,
        stream: str,
        line_text: str,
    ) -> SemanticOverflowExemptionKind | None:
        if stream not in {"stdout", "pty"}:
            return None
        payload = parse_repaired_ndjson_dict(line_text)
        if not isinstance(payload, dict):
            return None
        text = self.extract_text_event(payload)
        if isinstance(text, str) and text.strip():
            return "assistant_message"
        reasoning = self.extract_reasoning_text(payload)
        if isinstance(reasoning, str) and reasoning.strip():
            return "reasoning"
        return None

    def slice_latest_step_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return rows

        start_idx: int | None = None
        end_idx: int | None = None
        for idx, row in enumerate(rows):
            payload = row.get("payload")
            if not isinstance(payload, dict):
                continue
            if self.is_turn_start(payload):
                start_idx = idx
            elif self.is_turn_complete(payload) and start_idx is not None:
                end_idx = idx

        if start_idx is None:
            return rows
        if end_idx is not None and end_idx >= start_idx:
            return rows[start_idx : end_idx + 1]
        return rows[start_idx:]

    def extract_text_event(self, payload: dict[str, Any]) -> str | None:
        if payload.get("type") != "text":
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

    def extract_reasoning_text(self, payload: dict[str, Any]) -> str | None:
        if payload.get("type") != "reasoning":
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

    def is_turn_start(self, payload: dict[str, Any]) -> bool:
        return payload.get("type") in {"step_start", "step.started"}

    def is_turn_complete(self, payload: dict[str, Any]) -> bool:
        return payload.get("type") in {"step_finish", "step.completed"}

    def extract_turn_complete_data(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.is_turn_complete(payload):
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

    def extract_process_event(
        self,
        *,
        payload: dict[str, Any],
        row: dict[str, Any],
    ) -> RuntimeProcessEvent | None:
        reasoning = self.extract_reasoning_text(payload)
        if isinstance(reasoning, str) and reasoning.strip():
            part = payload.get("part")
            part_obj = part if isinstance(part, dict) else {}
            part_id = part_obj.get("id")
            byte_from = row.get("byte_from")
            message_id = (
                part_id
                if isinstance(part_id, str) and part_id.strip()
                else f"reasoning_{byte_from if isinstance(byte_from, int) else 0}"
            )
            raw_ref: RuntimeStreamRawRef = {
                "stream": str(row.get("stream")),
                "byte_from": int(row.get("byte_from") if isinstance(row.get("byte_from"), int) else 0),
                "byte_to": int(row.get("byte_to") if isinstance(row.get("byte_to"), int) else 0),
            }
            details: dict[str, Any] = {
                "payload_type": payload.get("type"),
                "item_type": "reasoning",
            }
            message_id_obj = part_obj.get("messageID")
            if isinstance(message_id_obj, str) and message_id_obj.strip():
                details["message_id"] = message_id_obj.strip()
            time_obj = part_obj.get("time")
            if isinstance(time_obj, dict):
                details["time"] = time_obj
            return {
                "process_type": "reasoning",
                "message_id": message_id,
                "summary": "reasoning",
                "classification": "reasoning",
                "details": details,
                "text": reasoning,
                "raw_ref": raw_ref,
            }
        if payload.get("type") != "tool_use":
            return None
        part = payload.get("part")
        if not isinstance(part, dict) or part.get("type") != "tool":
            return None
        tool_obj = part.get("tool")
        if not isinstance(tool_obj, str) or not tool_obj.strip():
            return None
        tool = tool_obj.strip()
        process_type = "command_execution" if tool in {"bash", "grep"} else "tool_call"

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
            if "metadata" in state:
                details["metadata"] = state.get("metadata")

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
                    text_value = (
                        input_obj
                        if isinstance(input_obj, str)
                        else json.dumps(input_obj, ensure_ascii=False)
                    )
                error_obj = state.get("error")
                if isinstance(error_obj, str) and error_obj.strip():
                    text_value = error_obj

        part_id = part.get("id")
        if isinstance(part_id, str) and part_id.strip():
            message_id = part_id
        else:
            byte_from = row.get("byte_from")
            message_id = f"{tool}_{byte_from if isinstance(byte_from, int) else 0}"
        raw_ref: RuntimeStreamRawRef = {
            "stream": str(row.get("stream")),
            "byte_from": int(row.get("byte_from") if isinstance(row.get("byte_from"), int) else 0),
            "byte_to": int(row.get("byte_to") if isinstance(row.get("byte_to"), int) else 0),
        }
        process_event: RuntimeProcessEvent = {
            "process_type": process_type,  # type: ignore[typeddict-item]
            "message_id": message_id,
            "summary": summary,
            "classification": process_type,
            "details": details,
            "raw_ref": raw_ref,
        }
        if isinstance(text_value, str) and text_value.strip():
            process_event["text"] = text_value
        return process_event

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
        records = self.slice_latest_step_rows(all_records)
        pty_records = self.slice_latest_step_rows(all_pty_records)

        assistant_messages: list[RuntimeAssistantMessage] = []
        process_events: list[RuntimeProcessEvent] = []
        diagnostics: list[str] = []
        structured_types: list[str] = []
        session_id: str | None = None
        turn_started = False
        turn_completed = False
        turn_failed = False
        turn_complete_data: dict[str, Any] | None = None
        turn_failure_data: dict[str, Any] | None = None
        start_ref: RuntimeStreamRawRef | None = None
        complete_ref: RuntimeStreamRawRef | None = None
        failed_ref: RuntimeStreamRawRef | None = None
        run_handle_id: str | None = None
        run_handle_ref: RuntimeStreamRawRef | None = None
        extracted: dict[str, Any] = {
            "error_name": None,
            "status_code": None,
            "message": None,
            "provider_id": self.fixed_provider_id,
            "response_error_type": None,
            "step_finish_unknown_count": 0,
            "saw_manual_interrupt": False,
        }

        def raw_ref_for(row: dict[str, Any]) -> RuntimeStreamRawRef:
            return {
                "stream": str(row["stream"]),
                "byte_from": int(row["byte_from"]),
                "byte_to": int(row["byte_to"]),
            }

        def accumulate(rows: list[dict[str, Any]]) -> None:
            nonlocal session_id, turn_failed, turn_failure_data, failed_ref
            for row in rows:
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    continue
                row_session_id = find_session_id(payload)
                if row_session_id and not session_id:
                    session_id = row_session_id
                payload_type = payload.get("type")
                if isinstance(payload_type, str):
                    structured_types.append(payload_type)
                if payload_type == "error":
                    error = payload.get("error")
                    if isinstance(error, dict):
                        extracted["error_name"] = error.get("name")
                        data = error.get("data")
                        if isinstance(data, dict):
                            extracted["status_code"] = data.get("statusCode")
                            extracted["message"] = data.get("message")
                            extracted["provider_id"] = data.get("providerID") or extracted.get(
                                "provider_id"
                            )
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
                    if self.error_extractor is not None and self.mark_error_rows_failed:
                        error_data = self.error_extractor(payload)
                        if error_data is not None and not turn_failed:
                            turn_failed = True
                            turn_failure_data = error_data
                            failed_ref = raw_ref_for(row)
                            extracted["error_name"] = error_data.get("error_name")
                            extracted["status_code"] = error_data.get("status_code")
                            extracted["message"] = error_data.get("message")
                            extracted["response_error_type"] = error_data.get("response_error_type")
                elif payload_type == "step_finish":
                    part = payload.get("part")
                    if isinstance(part, dict) and part.get("reason") == "unknown":
                        extracted["step_finish_unknown_count"] = int(
                            extracted["step_finish_unknown_count"]
                        ) + 1

        def consume_visible(rows: list[dict[str, Any]]) -> None:
            nonlocal session_id, turn_started, turn_completed, turn_complete_data
            nonlocal start_ref, complete_ref, run_handle_id, run_handle_ref
            for row in rows:
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    continue
                row_session_id = find_session_id(payload)
                if row_session_id and not session_id:
                    session_id = row_session_id
                raw_ref = raw_ref_for(row)
                if self.is_turn_start(payload) and not turn_started:
                    turn_started = True
                    start_ref = raw_ref
                if (
                    self.is_turn_start(payload)
                    and run_handle_id is None
                    and isinstance(row_session_id, str)
                    and row_session_id.strip()
                ):
                    run_handle_id = row_session_id.strip()
                    run_handle_ref = raw_ref
                if self.is_turn_complete(payload):
                    turn_completed = True
                    complete_ref = raw_ref
                    data = self.extract_turn_complete_data(payload)
                    if isinstance(data, dict):
                        turn_complete_data = data
                text = self.extract_text_event(payload)
                if isinstance(text, str) and text.strip():
                    assistant_messages.append({"text": text, "raw_ref": raw_ref})

        def consume_process(rows: list[dict[str, Any]]) -> None:
            for row in rows:
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    continue
                process_event = self.extract_process_event(payload=payload, row=row)
                if process_event is not None:
                    process_events.append(process_event)

        accumulate(all_records)
        accumulate(all_pty_records)
        consume_visible(records)
        consume_process(all_records)
        if not assistant_messages and pty_records:
            diagnostics.append("PTY_FALLBACK_USED")
            consume_visible(pty_records)
            consume_process(all_pty_records)
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
            engine=self.engine,
            rules=self.auth_rules,
            evidence={
                "engine": self.engine,
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
        if turn_started:
            turn_markers.append({"marker": "start", "raw_ref": start_ref})
        if turn_completed:
            complete_marker: RuntimeTurnMarker = {"marker": "complete", "raw_ref": complete_ref}
            if isinstance(turn_complete_data, dict):
                complete_marker["data"] = turn_complete_data
            turn_markers.append(complete_marker)
        if turn_failed:
            failed_marker: RuntimeTurnMarker = {"marker": "failed", "raw_ref": failed_ref}
            if isinstance(turn_failure_data, dict):
                failed_marker["data"] = turn_failure_data
            turn_markers.append(failed_marker)

        result: RuntimeStreamParseResult = {
            "parser": self.parser_name,
            "confidence": 0.95 if assistant_messages or process_events or turn_failed else 0.6,
            "session_id": session_id,
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "process_events": process_events,
            "turn_started": turn_started,
            "turn_completed": turn_completed,
            "turn_failed": turn_failed,
            "turn_markers": turn_markers,
            "raw_rows": raw_rows,
            "diagnostics": diagnostics,
            "structured_types": list(dict.fromkeys(structured_types)),
        }
        if isinstance(turn_complete_data, dict):
            result["turn_complete_data"] = turn_complete_data
        if isinstance(turn_failure_data, dict):
            result["turn_failure_data"] = turn_failure_data
        if isinstance(run_handle_id, str) and run_handle_id.strip():
            result["run_handle"] = {"handle_id": run_handle_id.strip(), "raw_ref": run_handle_ref}
        if auth_signal is not None:
            result["auth_signal"] = auth_signal
        return result

    def start_live_session(self) -> "_OpenCodeFamilyLiveSession":
        return _OpenCodeFamilyLiveSession(self)


class _OpenCodeFamilyLiveSession(NdjsonLiveStreamParserSession):
    def __init__(self, core: OpenCodeFamilyStreamParserCore) -> None:
        super().__init__(
            accepted_streams={"stdout", "pty"},
            overflow_exemption_probe=core.classify_ndjson_overflow_exemption,
        )
        self._core = core
        self._last_text: str | None = None
        self._turn_start_emitted = False
        self._turn_complete_emitted = False
        self._turn_failed_emitted = False
        self._run_handle_emitted = False

    def handle_live_row(
        self,
        *,
        payload: dict[str, Any],
        raw_ref: RuntimeStreamRawRef,
        stream: str,
    ) -> list[LiveParserEmission]:
        emissions: list[LiveParserEmission] = []
        session_id = find_session_id(payload)
        if self._core.is_turn_start(payload) and not self._turn_start_emitted:
            self._turn_start_emitted = True
            emissions.append({"kind": "turn_marker", "marker": "start", "raw_ref": raw_ref})
        if (
            self._core.is_turn_start(payload)
            and not self._run_handle_emitted
            and isinstance(session_id, str)
            and session_id.strip()
        ):
            self._run_handle_emitted = True
            emissions.append({"kind": "run_handle", "handle_id": session_id.strip(), "raw_ref": raw_ref})
        if self._core.is_turn_complete(payload) and not self._turn_complete_emitted:
            self._turn_complete_emitted = True
            turn_complete_data = self._core.extract_turn_complete_data(payload)
            marker: LiveParserEmission = {"kind": "turn_marker", "marker": "complete", "raw_ref": raw_ref}
            if isinstance(turn_complete_data, dict):
                marker["turn_complete_data"] = turn_complete_data
            emissions.append(marker)
            completed: LiveParserEmission = {"kind": "turn_completed"}
            if isinstance(turn_complete_data, dict):
                completed["turn_complete_data"] = turn_complete_data
            emissions.append(completed)
        if (
            self._core.error_extractor is not None
            and self._core.mark_error_rows_failed
            and not self._turn_failed_emitted
        ):
            error_data = self._core.error_extractor(payload)
            if error_data is not None:
                self._turn_failed_emitted = True
                emissions.append(
                    {
                        "kind": "turn_marker",
                        "marker": "failed",
                        "raw_ref": raw_ref,
                        "details": error_data,
                    }
                )
        row_for_process: dict[str, Any] = {
            "stream": stream,
            "byte_from": raw_ref["byte_from"],
            "byte_to": raw_ref["byte_to"],
        }
        process_event = self._core.extract_process_event(payload=payload, row=row_for_process)
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
        text = self._core.extract_text_event(payload)
        if not isinstance(text, str) or not text.strip() or text == self._last_text:
            return emissions
        self._last_text = text
        emission: LiveParserEmission = {
            "kind": "assistant_message",
            "text": text,
            "raw_ref": raw_ref,
        }
        if session_id:
            emission["session_id"] = session_id
        emissions.append(emission)
        return emissions
