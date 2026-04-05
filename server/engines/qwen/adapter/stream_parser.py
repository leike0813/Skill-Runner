from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from server.runtime.adapter.common.live_stream_parser_common import (
    NdjsonLiveStreamParserSession,
    parse_repaired_ndjson_dict,
    SemanticOverflowExemptionKind,
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
    RuntimeStreamRawRow,
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
    from .execution_adapter import QwenExecutionAdapter


def _summarize(value: str, *, limit: int = 220) -> str:
    compact = " ".join(value.replace("\r", "\n").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


class QwenStreamParser:
    """
    Stream parser for Qwen Code output.

    Qwen emits NDJSON semantic events on stdout while some auth banners are printed
    as plain text on stderr. This parser keeps those two responsibilities separate:
    - live session parsing only consumes stdout/pty NDJSON semantics
    - parse_runtime_stream inspects stdout/stderr/pty together for auth detection
    """

    _COMMAND_EXECUTION_TOOLS = {"run_shell_command"}

    def __init__(self, adapter: "QwenExecutionAdapter") -> None:
        self._adapter = adapter

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
        payload_type = str(payload.get("type") or "")
        if payload_type == "assistant":
            for block in self._assistant_content_blocks(payload):
                block_type = str(block.get("type") or "")
                if block_type == "thinking":
                    text_obj = block.get("thinking")
                    if isinstance(text_obj, str) and text_obj.strip():
                        return "reasoning"
                if block_type == "text":
                    text_obj = block.get("text")
                    if isinstance(text_obj, str) and text_obj.strip():
                        return "assistant_message"
            return None
        if payload_type == "result":
            text_obj = payload.get("result")
            if isinstance(text_obj, str) and text_obj.strip():
                return "assistant_message"
        return None

    @staticmethod
    def _raw_ref(row: dict[str, Any]) -> RuntimeStreamRawRef:
        return {
            "stream": str(row.get("stream") or "stdout"),
            "byte_from": int(row.get("byte_from") or 0),
            "byte_to": int(row.get("byte_to") or 0),
        }

    @staticmethod
    def _is_system_init(payload: dict[str, Any]) -> bool:
        return (
            str(payload.get("type") or "") == "system"
            and str(payload.get("subtype") or "") == "init"
        )

    @classmethod
    def _normalize_process_type(cls, *, tool_name: str | None) -> str:
        normalized = (tool_name or "").strip().lower()
        if normalized in cls._COMMAND_EXECUTION_TOOLS:
            return "command_execution"
        return "tool_call"

    @staticmethod
    def _normalize_text_key(value: str | None) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return normalized

    @staticmethod
    def _extract_turn_complete_data(payload: dict[str, Any]) -> dict[str, Any] | None:
        if str(payload.get("type") or "") != "result":
            return None
        data: dict[str, Any] = {}
        usage_obj = payload.get("usage")
        if isinstance(usage_obj, dict):
            data["usage"] = usage_obj
        subtype_obj = payload.get("subtype")
        if isinstance(subtype_obj, str) and subtype_obj.strip():
            data["result_subtype"] = subtype_obj.strip()
        return data or None

    @staticmethod
    def _assistant_content_blocks(payload: dict[str, Any]) -> list[dict[str, Any]]:
        if str(payload.get("type") or "") != "assistant":
            return []
        message_obj = payload.get("message")
        if not isinstance(message_obj, dict):
            return []
        content_obj = message_obj.get("content")
        if not isinstance(content_obj, list):
            return []
        return [block for block in content_obj if isinstance(block, dict)]

    @classmethod
    def _extract_assistant_text(cls, payload: dict[str, Any]) -> str | None:
        texts: list[str] = []
        for block in cls._assistant_content_blocks(payload):
            if str(block.get("type") or "") != "text":
                continue
            text_obj = block.get("text")
            if isinstance(text_obj, str) and text_obj.strip():
                texts.append(text_obj)
        if not texts:
            return None
        return "".join(texts)

    @staticmethod
    def _tool_summary(*, process_type: str, tool_name: str, tool_input: Any | None = None) -> str:
        if process_type == "command_execution" and isinstance(tool_input, dict):
            command_obj = tool_input.get("command")
            if isinstance(command_obj, str) and command_obj.strip():
                return command_obj.strip()
        if isinstance(tool_input, dict) and tool_name.strip().lower() == "skill":
            skill_obj = tool_input.get("skill")
            if isinstance(skill_obj, str) and skill_obj.strip():
                return skill_obj.strip()
        return _summarize(tool_name)

    @staticmethod
    def _build_thinking_process_event(
        *,
        row_raw_ref: RuntimeStreamRawRef,
        block: dict[str, Any],
    ) -> RuntimeProcessEvent | None:
        text = block.get("thinking")
        if not isinstance(text, str) or not text.strip():
            return None
        return {
            "process_type": cast(Any, "reasoning"),
            "message_id": f"thinking_{row_raw_ref['byte_from']}",
            "summary": _summarize(text),
            "classification": "reasoning",
            "details": {
                "payload_type": "assistant",
                "item_type": "thinking",
            },
            "text": text,
            "raw_ref": row_raw_ref,
        }

    @classmethod
    def _build_tool_use_process_event(
        cls,
        *,
        row_raw_ref: RuntimeStreamRawRef,
        block: dict[str, Any],
        tool_use_by_id: dict[str, dict[str, Any]],
    ) -> RuntimeProcessEvent | None:
        name = str(block.get("name") or "tool_use").strip() or "tool_use"
        tool_input = block.get("input")
        process_type = cls._normalize_process_type(tool_name=name)
        summary = cls._tool_summary(
            process_type=process_type,
            tool_name=name,
            tool_input=tool_input,
        )
        block_id = str(block.get("id") or "").strip()
        if block_id:
            tool_use_by_id[block_id] = {
                "tool_name": name,
                "process_type": process_type,
                "summary": summary,
                "input": tool_input,
            }
        text_value: str | None = None
        if tool_input is not None:
            if isinstance(tool_input, str):
                text_value = tool_input
            else:
                text_value = json.dumps(tool_input, ensure_ascii=False)
        return {
            "process_type": cast(Any, process_type),
            "message_id": block_id or name,
            "summary": summary,
            "classification": process_type,
            "details": {
                "payload_type": "assistant",
                "item_type": "tool_use",
                "tool_name": name,
                "input": tool_input,
            },
            "text": text_value,
            "raw_ref": row_raw_ref,
        }

    @classmethod
    def _build_tool_result_process_event(
        cls,
        *,
        row_raw_ref: RuntimeStreamRawRef,
        block: dict[str, Any],
        tool_use_by_id: dict[str, dict[str, Any]],
    ) -> RuntimeProcessEvent:
        tool_use_id = str(block.get("tool_use_id") or "").strip()
        tool_meta = tool_use_by_id.get(tool_use_id, {})
        tool_name = str(tool_meta.get("tool_name") or "").strip()
        process_type = str(tool_meta.get("process_type") or cls._normalize_process_type(tool_name=tool_name))
        summary = str(tool_meta.get("summary") or tool_name or "tool_result").strip() or "tool_result"
        content_value = block.get("content")
        text_value: str | None = None
        if isinstance(content_value, str) and content_value.strip():
            text_value = content_value
        elif content_value is not None:
            text_value = json.dumps(content_value, ensure_ascii=False)
        return {
            "process_type": cast(Any, process_type),
            "message_id": tool_use_id or summary,
            "summary": summary,
            "classification": process_type,
            "details": {
                "payload_type": "user",
                "item_type": "tool_result",
                "tool_use_id": tool_use_id or None,
                "tool_name": tool_name or None,
                "is_error": bool(block.get("is_error")),
            },
            "text": text_value,
            "raw_ref": row_raw_ref,
        }

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
            if isinstance(payload, dict):
                parsed_rows.append(payload)

        last_text = ""
        session_id: str | None = None
        for payload in parsed_rows:
            row_session_id = find_session_id(payload)
            if isinstance(row_session_id, str) and row_session_id and not session_id:
                session_id = row_session_id
            payload_type = str(payload.get("type") or "")
            if payload_type == "assistant":
                extracted = self._extract_assistant_text(payload)
                if isinstance(extracted, str) and extracted.strip():
                    last_text = extracted
            elif payload_type == "result":
                result_obj = payload.get("result")
                if isinstance(result_obj, str) and result_obj.strip():
                    last_text = result_obj

        source_text = last_text or raw_stdout
        result, repair_level = self._adapter._parse_json_with_deterministic_repair(
            source_text
        )  # noqa: SLF001
        if result is not None:
            turn_result = self._adapter._build_turn_result_from_payload(
                result, repair_level
            )  # noqa: SLF001
            structured_payload = self._adapter._materialize_output_payload(turn_result)  # noqa: SLF001
            turn_result_dict = turn_result.model_dump()
            if session_id:
                turn_result_dict["session_handle"] = {
                    "handle_type": "session_id",
                    "handle_value": session_id,
                }
            return {
                "turn_result": turn_result_dict,
                "structured_payload": structured_payload,
            }

        turn_result = self._adapter._turn_error(message="failed to parse qwen output")  # noqa: SLF001
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
    ) -> RuntimeStreamParseResult:
        stdout_rows = strip_runtime_script_envelope(stream_lines_with_offsets("stdout", stdout_raw))
        pty_rows = strip_runtime_script_envelope(stream_lines_with_offsets("pty", pty_raw))
        records, raw_rows = collect_json_parse_errors(stdout_rows)
        pty_records, pty_raw_rows = collect_json_parse_errors(pty_rows)

        assistant_messages: list[RuntimeAssistantMessage] = []
        process_events: list[RuntimeProcessEvent] = []
        diagnostics: list[str] = []
        session_id: str | None = None
        structured_types: list[str] = []
        turn_started = False
        turn_completed = False
        turn_complete_data: dict[str, Any] | None = None
        turn_start_raw_ref: RuntimeStreamRawRef | None = None
        turn_complete_raw_ref: RuntimeStreamRawRef | None = None
        run_handle_id: str | None = None
        run_handle_raw_ref: RuntimeStreamRawRef | None = None
        tool_use_by_id: dict[str, dict[str, Any]] = {}
        consumed_ranges: dict[str, list[tuple[int, int]]] = {"stdout": [], "stderr": [], "pty": []}
        seen_assistant_texts: set[str] = set()

        def _mark_consumed(raw_ref: RuntimeStreamRawRef | None) -> None:
            if not isinstance(raw_ref, dict):
                return
            stream = str(raw_ref.get("stream") or "stdout")
            byte_from = max(0, int(raw_ref.get("byte_from") or 0))
            byte_to = max(byte_from, int(raw_ref.get("byte_to") or byte_from))
            if byte_to <= byte_from:
                return
            consumed_ranges.setdefault(stream, []).append((byte_from, byte_to))

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

        def _append_assistant_message(*, text: str, raw_ref: RuntimeStreamRawRef, message_id: str | None = None) -> None:
            normalized = self._normalize_text_key(text)
            if normalized is None or normalized in seen_assistant_texts:
                return
            seen_assistant_texts.add(normalized)
            message: RuntimeAssistantMessage = {
                "text": text,
                "raw_ref": raw_ref,
            }
            if isinstance(message_id, str) and message_id.strip():
                message["message_id"] = message_id.strip()
            assistant_messages.append(message)

        def _collect(rows: list[dict[str, Any]]) -> None:
            nonlocal session_id, turn_started, turn_completed, turn_complete_data
            nonlocal turn_start_raw_ref, turn_complete_raw_ref, run_handle_id, run_handle_raw_ref
            for row in rows:
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    continue
                row_raw_ref = self._raw_ref(row)
                payload_type = str(payload.get("type") or "")
                if payload_type:
                    structured_types.append(payload_type)
                row_session_id = find_session_id(payload)
                if isinstance(row_session_id, str) and row_session_id and not session_id:
                    session_id = row_session_id
                if self._is_system_init(payload) and isinstance(row_session_id, str) and row_session_id.strip():
                    if not run_handle_id:
                        run_handle_id = row_session_id.strip()
                        run_handle_raw_ref = row_raw_ref
                    if not turn_started:
                        turn_started = True
                        if turn_start_raw_ref is None:
                            turn_start_raw_ref = row_raw_ref
                    _mark_consumed(row_raw_ref)
                    continue
                if isinstance(row_session_id, str) and row_session_id.strip() and not run_handle_id:
                    run_handle_id = row_session_id.strip()
                    run_handle_raw_ref = row_raw_ref
                if payload_type == "assistant":
                    if not turn_started:
                        turn_started = True
                        if turn_start_raw_ref is None:
                            turn_start_raw_ref = row_raw_ref
                    message_obj = payload.get("message")
                    message_id = (
                        str(message_obj.get("id") or "").strip()
                        if isinstance(message_obj, dict)
                        else ""
                    ) or None
                    consumed_this_row = False
                    for block in self._assistant_content_blocks(payload):
                        block_type = str(block.get("type") or "")
                        if block_type == "thinking":
                            process_event = self._build_thinking_process_event(
                                row_raw_ref=row_raw_ref,
                                block=block,
                            )
                            if process_event is not None:
                                process_events.append(process_event)
                                consumed_this_row = True
                        elif block_type == "tool_use":
                            process_event = self._build_tool_use_process_event(
                                row_raw_ref=row_raw_ref,
                                block=block,
                                tool_use_by_id=tool_use_by_id,
                            )
                            if process_event is not None:
                                process_events.append(process_event)
                                consumed_this_row = True
                        elif block_type == "text":
                            text_obj = block.get("text")
                            if isinstance(text_obj, str) and text_obj.strip():
                                _append_assistant_message(
                                    text=text_obj,
                                    raw_ref=row_raw_ref,
                                    message_id=message_id,
                                )
                                consumed_this_row = True
                    if consumed_this_row:
                        _mark_consumed(row_raw_ref)
                    continue
                if payload_type == "user":
                    message_obj = payload.get("message")
                    content_obj = message_obj.get("content") if isinstance(message_obj, dict) else None
                    consumed_this_row = False
                    if isinstance(content_obj, list):
                        for block in content_obj:
                            if not isinstance(block, dict):
                                continue
                            if str(block.get("type") or "") != "tool_result":
                                continue
                            process_events.append(
                                self._build_tool_result_process_event(
                                    row_raw_ref=row_raw_ref,
                                    block=block,
                                    tool_use_by_id=tool_use_by_id,
                                )
                            )
                            consumed_this_row = True
                    if consumed_this_row:
                        _mark_consumed(row_raw_ref)
                    continue
                if payload_type == "result":
                    if not turn_started:
                        turn_started = True
                        if turn_start_raw_ref is None:
                            turn_start_raw_ref = row_raw_ref
                    turn_completed = True
                    turn_complete_raw_ref = row_raw_ref
                    extracted_data = self._extract_turn_complete_data(payload)
                    if isinstance(extracted_data, dict):
                        turn_complete_data = extracted_data
                    result_text = payload.get("result")
                    if isinstance(result_text, str) and result_text.strip():
                        _append_assistant_message(text=result_text, raw_ref=row_raw_ref)
                    _mark_consumed(row_raw_ref)

        _collect(records)
        stdout_turn_completed = any(
            isinstance(row.get("payload"), dict) and str(row["payload"].get("type") or "") == "result"
            for row in records
        )
        pty_turn_completed = any(
            isinstance(row.get("payload"), dict) and str(row["payload"].get("type") or "") == "result"
            for row in pty_records
        )
        use_pty_fallback = (not assistant_messages and not process_events and pty_records) or (
            not stdout_turn_completed and pty_turn_completed
        )
        if use_pty_fallback:
            diagnostics.append("PTY_FALLBACK_USED")
            _collect(pty_records)

        raw_rows = [row for row in raw_rows if not _row_overlaps_consumed(row)]
        pty_raw_rows = [row for row in pty_raw_rows if not _row_overlaps_consumed(row)]
        raw_rows.extend(pty_raw_rows)
        if raw_rows:
            diagnostics.append("UNPARSED_CONTENT_FELL_BACK_TO_RAW")

        stdout_text = stdout_raw.decode("utf-8", errors="replace")
        stderr_text = stderr_raw.decode("utf-8", errors="replace")
        pty_text = pty_raw.decode("utf-8", errors="replace")
        combined_text = "\n".join(part for part in (stdout_text, stderr_text, pty_text) if part)
        auth_signal = detect_auth_signal_from_patterns(
            engine="qwen",
            rules=self._adapter.profile.parser_auth_patterns.rules,
            evidence={
                "engine": "qwen",
                "stdout_text": stdout_text,
                "stderr_text": stderr_text,
                "pty_output": pty_text,
                "combined_text": combined_text,
                "parser_diagnostics": list(dict.fromkeys(diagnostics)),
                "structured_types": list(dict.fromkeys(structured_types)),
                "extracted": {},
            },
        )

        turn_markers: list[RuntimeTurnMarker] = []
        if turn_started:
            turn_markers.append({"marker": "start", "raw_ref": turn_start_raw_ref})
        if turn_completed:
            marker: RuntimeTurnMarker = {"marker": "complete", "raw_ref": turn_complete_raw_ref}
            if isinstance(turn_complete_data, dict):
                marker["data"] = turn_complete_data
            turn_markers.append(marker)

        confidence = 0.95 if turn_completed else 0.75 if (assistant_messages or process_events or run_handle_id) else 0.5
        result: RuntimeStreamParseResult = {
            "parser": "qwen_ndjson",
            "confidence": confidence,
            "session_id": session_id,
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "process_events": process_events,
            "turn_started": turn_started,
            "turn_completed": turn_completed,
            "turn_markers": turn_markers,
            "raw_rows": raw_rows,
            "diagnostics": list(dict.fromkeys(diagnostics)),
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

    def start_live_session(self) -> "_QwenLiveSession":
        return _QwenLiveSession(self)


class _QwenLiveSession(NdjsonLiveStreamParserSession):
    """Live stream parser session for stdout/pty NDJSON semantics only."""

    def __init__(self, parser: QwenStreamParser) -> None:
        super().__init__(
            accepted_streams={"stdout", "pty"},
            overflow_exemption_probe=parser.classify_ndjson_overflow_exemption,
        )
        self._parser = parser
        self._turn_start_emitted = False
        self._turn_complete_emitted = False
        self._run_handle_emitted = False
        self._tool_use_by_id: dict[str, dict[str, Any]] = {}
        self._last_assistant_text_key: str | None = None

    def _build_process_emission(
        self,
        *,
        process_event: RuntimeProcessEvent,
        raw_ref: RuntimeStreamRawRef,
        session_id: str | None,
    ) -> LiveParserEmission:
        emission: LiveParserEmission = {
            "kind": "process_event",
            "process_type": process_event["process_type"],
            "summary": process_event["summary"],
            "classification": process_event.get("classification", process_event["process_type"]),
            "details": process_event.get("details", {}),
            "raw_ref": raw_ref,
        }
        message_id_obj = process_event.get("message_id")
        if isinstance(message_id_obj, str) and message_id_obj.strip():
            emission["message_id"] = message_id_obj
        text_obj = process_event.get("text")
        if isinstance(text_obj, str) and text_obj.strip():
            emission["text"] = text_obj
        if session_id:
            emission["session_id"] = session_id
        return emission

    def _append_assistant_emission(
        self,
        *,
        emissions: list[LiveParserEmission],
        text: str,
        raw_ref: RuntimeStreamRawRef,
        session_id: str | None,
        message_id: str | None = None,
    ) -> None:
        normalized = self._parser._normalize_text_key(text)  # noqa: SLF001
        if normalized is None or normalized == self._last_assistant_text_key:
            return
        self._last_assistant_text_key = normalized
        emission: LiveParserEmission = {
            "kind": "assistant_message",
            "text": text,
            "raw_ref": raw_ref,
        }
        if isinstance(message_id, str) and message_id.strip():
            emission["message_id"] = message_id.strip()
        if session_id:
            emission["session_id"] = session_id
        emissions.append(emission)

    def handle_live_row(
        self,
        *,
        payload: dict[str, Any],
        raw_ref: RuntimeStreamRawRef,
        stream: str,
    ) -> list[LiveParserEmission]:
        _ = stream
        emissions: list[LiveParserEmission] = []
        payload_type = str(payload.get("type") or "")
        session_id = find_session_id(payload)

        if self._parser._is_system_init(payload):  # noqa: SLF001
            if session_id and not self._run_handle_emitted:
                self._run_handle_emitted = True
                emissions.append(
                    {
                        "kind": "run_handle",
                        "handle_id": session_id,
                        "raw_ref": raw_ref,
                        "session_id": session_id,
                    }
                )
            if not self._turn_start_emitted:
                self._turn_start_emitted = True
                marker: LiveParserEmission = {
                    "kind": "turn_marker",
                    "marker": "start",
                    "raw_ref": raw_ref,
                }
                if session_id:
                    marker["session_id"] = session_id
                emissions.append(marker)
            return emissions

        if payload_type == "assistant":
            if not self._turn_start_emitted:
                self._turn_start_emitted = True
                start_marker: LiveParserEmission = {
                    "kind": "turn_marker",
                    "marker": "start",
                    "raw_ref": raw_ref,
                }
                if session_id:
                    start_marker["session_id"] = session_id
                emissions.append(start_marker)
            message_obj = payload.get("message")
            message_id = (
                str(message_obj.get("id") or "").strip()
                if isinstance(message_obj, dict)
                else ""
            ) or None
            for block in self._parser._assistant_content_blocks(payload):  # noqa: SLF001
                block_type = str(block.get("type") or "")
                if block_type == "thinking":
                    process_event = self._parser._build_thinking_process_event(  # noqa: SLF001
                        row_raw_ref=raw_ref,
                        block=block,
                    )
                    if process_event is not None:
                        emissions.append(
                            self._build_process_emission(
                                process_event=process_event,
                                raw_ref=raw_ref,
                                session_id=session_id,
                            )
                        )
                elif block_type == "tool_use":
                    process_event = self._parser._build_tool_use_process_event(  # noqa: SLF001
                        row_raw_ref=raw_ref,
                        block=block,
                        tool_use_by_id=self._tool_use_by_id,
                    )
                    if process_event is not None:
                        emissions.append(
                            self._build_process_emission(
                                process_event=process_event,
                                raw_ref=raw_ref,
                                session_id=session_id,
                            )
                        )
                elif block_type == "text":
                    text_obj = block.get("text")
                    if isinstance(text_obj, str) and text_obj.strip():
                        self._append_assistant_emission(
                            emissions=emissions,
                            text=text_obj,
                            raw_ref=raw_ref,
                            session_id=session_id,
                            message_id=message_id,
                        )
            return emissions

        if payload_type == "user":
            message_obj = payload.get("message")
            content_obj = message_obj.get("content") if isinstance(message_obj, dict) else None
            if isinstance(content_obj, list):
                for block in content_obj:
                    if not isinstance(block, dict):
                        continue
                    if str(block.get("type") or "") != "tool_result":
                        continue
                    process_event = self._parser._build_tool_result_process_event(  # noqa: SLF001
                        row_raw_ref=raw_ref,
                        block=block,
                        tool_use_by_id=self._tool_use_by_id,
                    )
                    emissions.append(
                        self._build_process_emission(
                            process_event=process_event,
                            raw_ref=raw_ref,
                            session_id=session_id,
                        )
                    )
            return emissions

        if payload_type == "result":
            result_text = payload.get("result")
            if isinstance(result_text, str) and result_text.strip():
                self._append_assistant_emission(
                    emissions=emissions,
                    text=result_text,
                    raw_ref=raw_ref,
                    session_id=session_id,
                )
            if not self._turn_complete_emitted:
                self._turn_complete_emitted = True
                turn_complete_data = self._parser._extract_turn_complete_data(payload)  # noqa: SLF001
                marker_emission: LiveParserEmission = {
                    "kind": "turn_marker",
                    "marker": "complete",
                    "raw_ref": raw_ref,
                }
                if isinstance(turn_complete_data, dict):
                    marker_emission["turn_complete_data"] = turn_complete_data
                if session_id:
                    marker_emission["session_id"] = session_id
                emissions.append(marker_emission)
                completion_emission: LiveParserEmission = {"kind": "turn_completed"}
                if isinstance(turn_complete_data, dict):
                    completion_emission["turn_complete_data"] = turn_complete_data
                if session_id:
                    completion_emission["session_id"] = session_id
                emissions.append(completion_emission)
        return emissions
