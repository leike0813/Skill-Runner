from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, cast

from server.runtime.adapter.common.live_stream_parser_common import (
    NdjsonLiveStreamParserSession,
    parse_repaired_ndjson_dict,
    SemanticOverflowExemptionKind,
)
from server.runtime.adapter.common.parser_auth_signal_matcher import detect_auth_signal_from_patterns
from server.runtime.adapter.types import (
    LiveParserEmission,
    RuntimeAssistantMessage,
    RuntimeProcessEvent,
    RuntimeStreamRawRef,
    RuntimeStreamRawRow,
)
from server.runtime.protocol.parse_utils import (
    collect_json_parse_errors,
    dedup_assistant_messages,
    find_session_id,
    stream_lines_with_offsets,
    strip_runtime_script_envelope,
)

if TYPE_CHECKING:
    from .execution_adapter import ClaudeExecutionAdapter


def _summarize(value: str, *, limit: int = 220) -> str:
    compact = " ".join(value.replace("\r", "\n").split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


_CLAUDE_SANDBOX_DEPENDENCY_MISSING = "CLAUDE_SANDBOX_DEPENDENCY_MISSING"
_CLAUDE_SANDBOX_RUNTIME_FAILURE = "CLAUDE_SANDBOX_RUNTIME_FAILURE"
_CLAUDE_SANDBOX_POLICY_VIOLATION = "CLAUDE_SANDBOX_POLICY_VIOLATION"
_SANDBOX_RUNTIME_FAILURE_PATTERNS = (
    r"\bbwrap:.*failed rtm_newaddr",
    r"\bbwrap:.*operation not permitted",
    r"\bbwrap:.*creating new namespace failed",
    r"\bbubblewrap:.*operation not permitted",
    r"\bbubblewrap:.*creating new namespace failed",
)


class ClaudeStreamParser:
    def __init__(self, adapter: "ClaudeExecutionAdapter") -> None:
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
            message_obj = payload.get("message")
            content_obj = message_obj.get("content") if isinstance(message_obj, dict) else None
            if not isinstance(content_obj, list):
                return None
            for block in content_obj:
                if not isinstance(block, dict):
                    continue
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
        return None

    @staticmethod
    def _result_has_structured_output(payload: dict[str, Any]) -> bool:
        return "structured_output" in payload and payload.get("structured_output") is not None

    def _structured_output_result_enabled(self) -> bool:
        return (
            self._adapter.profile.structured_output.result_success_strategy
            == "result_structured_output_field"
        )

    def _build_structured_output_result_message(
        self,
        *,
        payload: dict[str, Any],
        row_raw_ref: RuntimeStreamRawRef,
    ) -> RuntimeAssistantMessage | None:
        if not self._structured_output_result_enabled():
            return None
        if str(payload.get("subtype") or "").strip().lower() != "success":
            return None
        structured = payload.get("structured_output")
        if not isinstance(structured, dict):
            return None
        try:
            text = json.dumps(structured, ensure_ascii=False)
        except (TypeError, ValueError):
            return None
        if not text.strip():
            return None
        return {
            "text": text,
            "raw_ref": row_raw_ref,
            "details": {"source": "structured_output_result"},
        }

    @classmethod
    def _should_emit_result_text_fallback(
        cls,
        *,
        payload: dict[str, Any],
        assistant_text_seen: bool,
    ) -> bool:
        if assistant_text_seen:
            return False
        if cls._result_has_structured_output(payload):
            return False
        text_obj = payload.get("result")
        return isinstance(text_obj, str) and bool(text_obj.strip())

    @staticmethod
    def _raw_ref(row: dict[str, Any]) -> RuntimeStreamRawRef:
        return {
            "stream": str(row.get("stream") or "stdout"),
            "byte_from": int(row.get("byte_from") or 0),
            "byte_to": int(row.get("byte_to") or 0),
        }

    @staticmethod
    def _normalize_process_type(*, tool_name: str | None, tool_result: Any | None = None) -> str:
        normalized = (tool_name or "").strip().lower()
        if normalized in {"bash", "grep"}:
            return "command_execution"
        if isinstance(tool_result, dict) and any(key in tool_result for key in ("stdout", "stderr")):
            return "command_execution"
        if isinstance(tool_result, str) and "Exit code" in tool_result:
            return "command_execution"
        return "tool_call"

    @staticmethod
    def _tool_summary(*, process_type: str, tool_name: str, tool_input: Any | None = None) -> str:
        if process_type == "command_execution" and isinstance(tool_input, dict):
            command_obj = tool_input.get("command")
            if isinstance(command_obj, str) and command_obj.strip():
                return command_obj.strip()
        if isinstance(tool_input, dict):
            if tool_name.strip().lower() == "skill":
                skill_obj = tool_input.get("skill")
                if isinstance(skill_obj, str) and skill_obj.strip():
                    return skill_obj.strip()
        return _summarize(tool_name)

    @staticmethod
    def _build_thinking_process_event(
        *,
        row_raw_ref: RuntimeStreamRawRef,
        payload_type: str,
        block: dict[str, Any],
    ) -> RuntimeProcessEvent | None:
        text = block.get("thinking")
        if not isinstance(text, str) or not text.strip():
            text = block.get("text")
        if not isinstance(text, str) or not text.strip():
            return None
        return {
            "process_type": cast(Any, "reasoning"),
            "message_id": f"thinking_{row_raw_ref['byte_from']}",
            "summary": _summarize(text),
            "classification": "reasoning",
            "details": {
                "payload_type": payload_type,
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
        payload_type: str,
        block: dict[str, Any],
        tool_use_by_id: dict[str, dict[str, Any]],
    ) -> RuntimeProcessEvent | None:
        name = str(block.get("name") or "tool_use")
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
        return {
            "process_type": cast(Any, process_type),
            "message_id": block_id or name,
            "summary": summary,
            "classification": process_type,
            "details": {
                "payload_type": payload_type,
                "item_type": "tool_use",
                "tool_name": name,
                "input": tool_input,
            },
            "text": json.dumps(tool_input, ensure_ascii=False)
            if tool_input is not None
            else None,
            "raw_ref": row_raw_ref,
        }

    @classmethod
    def _build_tool_result_process_event(
        cls,
        *,
        row_raw_ref: RuntimeStreamRawRef,
        payload_type: str,
        block: dict[str, Any],
        tool_result: Any | None,
        tool_use_by_id: dict[str, dict[str, Any]],
    ) -> RuntimeProcessEvent:
        tool_use_id = str(block.get("tool_use_id") or "").strip()
        tool_meta = tool_use_by_id.get(tool_use_id, {})
        tool_result_command_name: str | None = None
        if isinstance(tool_result, dict):
            command_name_obj = tool_result.get("commandName")
            if isinstance(command_name_obj, str) and command_name_obj.strip():
                tool_result_command_name = command_name_obj.strip()
        tool_name = str(tool_meta.get("tool_name") or tool_result_command_name or "").strip()
        process_type = cls._normalize_process_type(
            tool_name=tool_name or None,
            tool_result=tool_result,
        )
        summary = str(tool_meta.get("summary") or tool_name or "tool_result").strip() or "tool_result"
        content_value = block.get("content")
        text_value: str | None = None
        if isinstance(content_value, str) and content_value.strip():
            text_value = content_value
        elif content_value is not None:
            text_value = json.dumps(content_value, ensure_ascii=False)
        elif tool_result is not None:
            text_value = (
                tool_result
                if isinstance(tool_result, str)
                else json.dumps(tool_result, ensure_ascii=False)
            )
        process_details: dict[str, Any] = {
            "payload_type": payload_type,
            "item_type": "tool_result",
            "tool_use_id": tool_use_id or None,
            "is_error": bool(block.get("is_error")),
        }
        if tool_name:
            process_details["tool_name"] = tool_name
        if tool_result is not None:
            process_details["tool_use_result"] = tool_result
        return {
            "process_type": cast(Any, process_type),
            "message_id": tool_use_id or summary,
            "summary": summary,
            "classification": process_type,
            "details": process_details,
            "text": text_value,
            "raw_ref": row_raw_ref,
        }

    @staticmethod
    def _parse_rows(text: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
        return rows

    @staticmethod
    def _mark_consumed(
        consumed_ranges: dict[str, list[tuple[int, int]]],
        raw_ref: RuntimeStreamRawRef | None,
    ) -> None:
        if not isinstance(raw_ref, dict):
            return
        stream = str(raw_ref.get("stream") or "stdout")
        start = max(0, int(raw_ref.get("byte_from") or 0))
        end = max(start, int(raw_ref.get("byte_to") or start))
        consumed_ranges.setdefault(stream, []).append((start, end))

    @staticmethod
    def _row_overlaps_consumed(
        consumed_ranges: dict[str, list[tuple[int, int]]],
        row: dict[str, Any] | RuntimeStreamRawRow,
    ) -> bool:
        ranges = consumed_ranges.get(str(row.get("stream") or "stdout"), [])
        if not ranges:
            return False
        row_start = max(0, int(row.get("byte_from") or 0))
        row_end = max(row_start, int(row.get("byte_to") or row_start))
        for start, end in ranges:
            if row_start < end and row_end > start:
                return True
        return False

    @staticmethod
    def _collect_sandbox_diagnostics(
        *,
        combined_text: str,
        process_events: list[RuntimeProcessEvent],
    ) -> list[str]:
        diagnostics: list[str] = []
        lowered = combined_text.lower()

        if re.search(r"\b(?:bwrap|bubblewrap|socat)\b.*(?:command not found|not found)", lowered):
            diagnostics.append(_CLAUDE_SANDBOX_DEPENDENCY_MISSING)
        if re.search(r"\b(?:bwrap|bubblewrap|socat)\b.*no such file or directory", lowered):
            diagnostics.append(_CLAUDE_SANDBOX_DEPENDENCY_MISSING)

        if any(re.search(pattern, lowered) for pattern in _SANDBOX_RUNTIME_FAILURE_PATTERNS):
            diagnostics.append(_CLAUDE_SANDBOX_RUNTIME_FAILURE)

        for item in process_events:
            if str(item.get("classification") or "") != "command_execution":
                continue
            text = str(item.get("text") or "")
            details = item.get("details")
            is_error = isinstance(details, dict) and bool(details.get("is_error"))
            lowered_text = text.lower()
            if not is_error:
                continue
            if any(re.search(pattern, lowered_text) for pattern in _SANDBOX_RUNTIME_FAILURE_PATTERNS):
                diagnostics.append(_CLAUDE_SANDBOX_RUNTIME_FAILURE)
                continue
            if (
                "sandbox policy" in lowered_text
                or "blocked by sandbox" in lowered_text
                or "permission denied" in lowered_text
                or "read-only file system" in lowered_text
                or "disallowed network" in lowered_text
                or "outside permitted paths" in lowered_text
                or "sensitive/system" in lowered_text
            ):
                diagnostics.append(_CLAUDE_SANDBOX_POLICY_VIOLATION)
                break

        return list(dict.fromkeys(diagnostics))

    def parse(self, raw_stdout: str) -> dict[str, object]:
        rows = self._parse_rows(raw_stdout)
        structured: Any | None = None
        result_text = ""
        for payload in rows:
            if str(payload.get("type") or "") != "result":
                continue
            if payload.get("subtype") == "success" and "structured_output" in payload:
                structured = payload.get("structured_output")
            result_obj = payload.get("result")
            if isinstance(result_obj, str) and result_obj.strip():
                result_text = result_obj

        if isinstance(structured, dict):
            turn_result = self._adapter._build_turn_result_from_payload(structured, "none")  # noqa: SLF001
            structured_payload = self._adapter._materialize_output_payload(turn_result)  # noqa: SLF001
            return {"turn_result": turn_result.model_dump(), "structured_payload": structured_payload}

        candidate_text = result_text or raw_stdout
        result, repair_level = self._adapter._parse_json_with_deterministic_repair(candidate_text)  # noqa: SLF001
        if isinstance(result, dict):
            turn_result = self._adapter._build_turn_result_from_payload(result, repair_level)  # noqa: SLF001
            structured_payload = self._adapter._materialize_output_payload(turn_result)  # noqa: SLF001
            return {"turn_result": turn_result.model_dump(), "structured_payload": structured_payload}
        turn_result = self._adapter._turn_error(message="failed to parse claude output")  # noqa: SLF001
        return {"turn_result": turn_result.model_dump(), "structured_payload": None}

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
        assistant_messages: list[RuntimeAssistantMessage] = []
        process_events: list[RuntimeProcessEvent] = []
        diagnostics: list[str] = []
        session_id: str | None = None
        structured_types: list[str] = []
        turn_started = False
        turn_completed = False
        turn_complete_data: dict[str, Any] | None = None
        turn_markers: list[dict[str, Any]] = []
        run_handle: dict[str, Any] | None = None
        tool_use_by_id: dict[str, dict[str, Any]] = {}
        turn_start_raw_ref: RuntimeStreamRawRef | None = None
        turn_complete_raw_ref: RuntimeStreamRawRef | None = None
        consumed_ranges: dict[str, list[tuple[int, int]]] = {"stdout": [], "stderr": [], "pty": []}
        assistant_text_seen = False

        def _collect(rows: list[dict[str, Any]]) -> None:
            nonlocal session_id, turn_started, turn_completed, turn_complete_data, run_handle, turn_start_raw_ref, turn_complete_raw_ref, assistant_text_seen
            for row in rows:
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    continue
                row_raw_ref = self._raw_ref(row)
                payload_type = str(payload.get("type") or "")
                if payload_type:
                    structured_types.append(payload_type)
                payload_session_id = find_session_id(payload)
                if payload_session_id and not session_id:
                    session_id = payload_session_id
                if payload_session_id and run_handle is None:
                    run_handle = {
                        "handle_id": payload_session_id,
                        "raw_ref": row_raw_ref,
                    }
                    self._mark_consumed(consumed_ranges, row_raw_ref)
                if payload_type == "system" and str(payload.get("subtype") or "") == "init":
                    turn_started = True
                    if turn_start_raw_ref is None:
                        turn_start_raw_ref = row_raw_ref
                    self._mark_consumed(consumed_ranges, row_raw_ref)
                if payload_type == "assistant":
                    turn_started = True
                    if turn_start_raw_ref is None:
                        turn_start_raw_ref = row_raw_ref
                    content = payload.get("message", {}).get("content") if isinstance(payload.get("message"), dict) else None
                    if isinstance(content, list):
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            block_type = str(block.get("type") or "")
                            if block_type == "thinking":
                                process_event = self._build_thinking_process_event(
                                    row_raw_ref=row_raw_ref,
                                    payload_type=payload_type,
                                    block=block,
                                )
                                if process_event is not None:
                                    process_events.append(process_event)
                                    self._mark_consumed(consumed_ranges, row_raw_ref)
                            elif block_type == "text":
                                text = block.get("text")
                                if isinstance(text, str) and text.strip():
                                    assistant_text_seen = True
                                    self._mark_consumed(consumed_ranges, row_raw_ref)
                                    assistant_messages.append(
                                        {
                                            "text": text,
                                            "raw_ref": row_raw_ref,
                                        }
                                    )
                            elif block_type == "tool_use":
                                process_event = self._build_tool_use_process_event(
                                    row_raw_ref=row_raw_ref,
                                    payload_type=payload_type,
                                    block=block,
                                    tool_use_by_id=tool_use_by_id,
                                )
                                if process_event is not None:
                                    process_events.append(process_event)
                                self._mark_consumed(consumed_ranges, row_raw_ref)
                elif payload_type == "user":
                    content = payload.get("message", {}).get("content") if isinstance(payload.get("message"), dict) else None
                    if isinstance(content, list):
                        for block in content:
                            if not isinstance(block, dict) or str(block.get("type") or "") != "tool_result":
                                continue
                            tool_result = payload.get("tool_use_result")
                            process_events.append(
                                self._build_tool_result_process_event(
                                    row_raw_ref=row_raw_ref,
                                    payload_type=payload_type,
                                    block=block,
                                    tool_result=tool_result,
                                    tool_use_by_id=tool_use_by_id,
                                )
                            )
                            self._mark_consumed(consumed_ranges, row_raw_ref)
                elif payload_type == "result":
                    turn_started = True
                    turn_completed = True
                    if turn_start_raw_ref is None:
                        turn_start_raw_ref = row_raw_ref
                    turn_complete_raw_ref = row_raw_ref
                    usage_obj = payload.get("usage")
                    turn_complete_data = dict(usage_obj) if isinstance(usage_obj, dict) else {}
                    subtype_obj = payload.get("subtype")
                    if isinstance(subtype_obj, str) and subtype_obj.strip():
                        turn_complete_data["result_subtype"] = subtype_obj.strip()
                    structured_output_message = self._build_structured_output_result_message(
                        payload=payload,
                        row_raw_ref=row_raw_ref,
                    )
                    if structured_output_message is not None:
                        assistant_text_seen = True
                        assistant_messages.append(structured_output_message)
                        self._mark_consumed(consumed_ranges, row_raw_ref)
                    text = payload.get("result")
                    if self._should_emit_result_text_fallback(
                        payload=payload,
                        assistant_text_seen=assistant_text_seen,
                    ) and isinstance(text, str):
                        assistant_text_seen = True
                        self._mark_consumed(consumed_ranges, row_raw_ref)
                        assistant_messages.append(
                            {
                                "text": text,
                                "raw_ref": row_raw_ref,
                                "details": {"source": "claude_result_fallback"},
                            }
                        )
                    self._mark_consumed(consumed_ranges, row_raw_ref)

        _collect(cast(list[dict[str, Any]], records))
        if not assistant_messages and pty_records:
            diagnostics.append("PTY_FALLBACK_USED")
            _collect(cast(list[dict[str, Any]], pty_records))
        raw_rows.extend(pty_raw_rows)
        raw_rows = [
            row
            for row in raw_rows
            if not self._row_overlaps_consumed(consumed_ranges, row)
        ]
        if raw_rows:
            diagnostics.append("UNPARSED_CONTENT_FELL_BACK_TO_RAW")

        stdout_text = stdout_raw.decode("utf-8", errors="replace")
        stderr_text = stderr_raw.decode("utf-8", errors="replace")
        pty_text = pty_raw.decode("utf-8", errors="replace")
        combined_text = "\n".join(part for part in (stdout_text, stderr_text, pty_text) if part)
        diagnostics.extend(
            self._collect_sandbox_diagnostics(
                combined_text=combined_text,
                process_events=process_events,
            )
        )
        auth_signal = detect_auth_signal_from_patterns(
            engine="claude",
            rules=self._adapter.profile.parser_auth_patterns.rules,
            evidence={
                "engine": "claude",
                "stdout_text": stdout_text,
                "stderr_text": stderr_text,
                "pty_output": pty_text,
                "combined_text": combined_text,
                "parser_diagnostics": list(dict.fromkeys(diagnostics)),
                "structured_types": list(dict.fromkeys(structured_types)),
                "extracted": {},
            },
        )

        if turn_started:
            turn_markers.append({"marker": "start", "raw_ref": turn_start_raw_ref})
        if turn_completed:
            marker: dict[str, Any] = {"marker": "complete", "raw_ref": turn_complete_raw_ref}
            if isinstance(turn_complete_data, dict):
                marker["data"] = turn_complete_data
            turn_markers.append(marker)

        result: dict[str, object] = {
            "parser": "claude_stream_json",
            "confidence": 0.95 if turn_completed else 0.75 if (assistant_messages or process_events or run_handle) else 0.5,
            "session_id": session_id,
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "process_events": process_events,
            "turn_started": turn_started,
            "turn_completed": turn_completed,
            "turn_markers": turn_markers,
            "raw_rows": list(raw_rows),
            "diagnostics": diagnostics,
            "structured_types": list(dict.fromkeys(structured_types)),
        }
        if isinstance(turn_complete_data, dict):
            result["turn_complete_data"] = turn_complete_data
        if run_handle is not None:
            result["run_handle"] = run_handle
        if auth_signal is not None:
            result["auth_signal"] = auth_signal
        return result

    def start_live_session(self) -> "_ClaudeLiveSession":
        return _ClaudeLiveSession(self)


class _ClaudeLiveSession(NdjsonLiveStreamParserSession):
    def __init__(self, parser: ClaudeStreamParser) -> None:
        super().__init__(
            accepted_streams={"stdout", "pty"},
            overflow_exemption_probe=parser.classify_ndjson_overflow_exemption,
        )
        self._parser = parser
        self._run_handle_emitted = False
        self._turn_start_emitted = False
        self._turn_complete_emitted = False
        self._assistant_text_seen = False
        self._tool_use_by_id: dict[str, dict[str, Any]] = {}

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
        payload_session_id = find_session_id(payload)
        if (
            payload_session_id
            and not self._run_handle_emitted
        ):
            self._run_handle_emitted = True
            emissions.append(
                {
                    "kind": "run_handle",
                    "handle_id": payload_session_id,
                    "raw_ref": raw_ref,
                    "session_id": payload_session_id,
                }
            )
        if payload_type == "system" and str(payload.get("subtype") or "") == "init" and not self._turn_start_emitted:
            self._turn_start_emitted = True
            marker: LiveParserEmission = {
                "kind": "turn_marker",
                "marker": "start",
                "raw_ref": raw_ref,
            }
            if payload_session_id:
                marker["session_id"] = payload_session_id
            emissions.append(marker)
            return emissions
        if payload_type == "assistant":
            content = payload.get("message", {}).get("content") if isinstance(payload.get("message"), dict) else None
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    block_type = str(block.get("type") or "")
                    if block_type == "thinking":
                        process_event = self._parser._build_thinking_process_event(  # noqa: SLF001
                            row_raw_ref=raw_ref,
                            payload_type=payload_type,
                            block=block,
                        )
                        if process_event is None:
                            continue
                        thinking_emission: LiveParserEmission = {
                            "kind": "process_event",
                            "process_type": process_event["process_type"],
                            "summary": process_event["summary"],
                            "classification": process_event.get("classification", process_event["process_type"]),
                            "details": process_event.get("details", {}),
                            "raw_ref": raw_ref,
                        }
                        message_id_obj = process_event.get("message_id")
                        if isinstance(message_id_obj, str) and message_id_obj.strip():
                            thinking_emission["message_id"] = message_id_obj
                        text_obj = process_event.get("text")
                        if isinstance(text_obj, str) and text_obj.strip():
                            thinking_emission["text"] = text_obj
                        if payload_session_id:
                            thinking_emission["session_id"] = payload_session_id
                        emissions.append(thinking_emission)
                    elif block_type == "text":
                        text = block.get("text")
                        if isinstance(text, str) and text.strip():
                            self._assistant_text_seen = True
                            emission: LiveParserEmission = {
                                "kind": "assistant_message",
                                "text": text,
                                "raw_ref": raw_ref,
                            }
                            if payload_session_id:
                                emission["session_id"] = payload_session_id
                            emissions.append(emission)
                    elif block_type == "tool_use":
                        process_event = self._parser._build_tool_use_process_event(  # noqa: SLF001
                            row_raw_ref=raw_ref,
                            payload_type=payload_type,
                            block=block,
                            tool_use_by_id=self._tool_use_by_id,
                        )
                        if process_event is None:
                            continue
                        tool_use_emission: LiveParserEmission = {
                            "kind": "process_event",
                            "process_type": process_event["process_type"],
                            "summary": process_event["summary"],
                            "classification": process_event.get("classification", process_event["process_type"]),
                            "details": process_event.get("details", {}),
                            "raw_ref": raw_ref,
                        }
                        message_id_obj = process_event.get("message_id")
                        if isinstance(message_id_obj, str) and message_id_obj.strip():
                            tool_use_emission["message_id"] = message_id_obj
                        text_obj = process_event.get("text")
                        if isinstance(text_obj, str) and text_obj.strip():
                            tool_use_emission["text"] = text_obj
                        if payload_session_id:
                            tool_use_emission["session_id"] = payload_session_id
                        emissions.append(tool_use_emission)
            return emissions
        if payload_type == "user":
            content = payload.get("message", {}).get("content") if isinstance(payload.get("message"), dict) else None
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict) or str(block.get("type") or "") != "tool_result":
                        continue
                    process_event = self._parser._build_tool_result_process_event(  # noqa: SLF001
                        row_raw_ref=raw_ref,
                        payload_type=payload_type,
                        block=block,
                        tool_result=payload.get("tool_use_result"),
                        tool_use_by_id=self._tool_use_by_id,
                    )
                    tool_result_emission: LiveParserEmission = {
                        "kind": "process_event",
                        "process_type": process_event["process_type"],
                        "summary": process_event["summary"],
                        "classification": process_event.get("classification", process_event["process_type"]),
                        "details": process_event.get("details", {}),
                        "raw_ref": raw_ref,
                    }
                    message_id_obj = process_event.get("message_id")
                    if isinstance(message_id_obj, str) and message_id_obj.strip():
                        tool_result_emission["message_id"] = message_id_obj
                    text_obj = process_event.get("text")
                    if isinstance(text_obj, str) and text_obj.strip():
                        tool_result_emission["text"] = text_obj
                    if payload_session_id:
                        tool_result_emission["session_id"] = payload_session_id
                    emissions.append(tool_result_emission)
            return emissions
        if payload_type == "result" and not self._turn_complete_emitted:
            self._turn_complete_emitted = True
            structured_output_message = self._parser._build_structured_output_result_message(  # noqa: SLF001
                payload=payload,
                row_raw_ref=raw_ref,
            )
            if structured_output_message is not None:
                self._assistant_text_seen = True
                structured_output_emission: LiveParserEmission = {
                    "kind": "assistant_message",
                    "text": structured_output_message["text"],
                    "details": structured_output_message.get("details", {}),
                    "raw_ref": raw_ref,
                }
                if payload_session_id:
                    structured_output_emission["session_id"] = payload_session_id
                emissions.append(structured_output_emission)
            text = payload.get("result")
            if self._parser._should_emit_result_text_fallback(  # noqa: SLF001
                payload=payload,
                assistant_text_seen=self._assistant_text_seen,
            ) and isinstance(text, str):
                self._assistant_text_seen = True
                result_message_emission: LiveParserEmission = {
                    "kind": "assistant_message",
                    "text": text,
                    "details": {"source": "claude_result_fallback"},
                    "raw_ref": raw_ref,
                }
                if payload_session_id:
                    result_message_emission["session_id"] = payload_session_id
                emissions.append(result_message_emission)
            turn_complete_data: dict[str, Any] = {}
            usage_obj = payload.get("usage")
            if isinstance(usage_obj, dict):
                turn_complete_data.update(dict(usage_obj))
            subtype_obj = payload.get("subtype")
            if isinstance(subtype_obj, str) and subtype_obj.strip():
                turn_complete_data["result_subtype"] = subtype_obj.strip()
            marker_emission: LiveParserEmission = {
                "kind": "turn_marker",
                "marker": "complete",
                "raw_ref": raw_ref,
            }
            if turn_complete_data:
                marker_emission["turn_complete_data"] = turn_complete_data
            if payload_session_id:
                marker_emission["session_id"] = payload_session_id
            emissions.append(marker_emission)
            completion_emission: LiveParserEmission = {"kind": "turn_completed"}
            if turn_complete_data:
                completion_emission["turn_complete_data"] = turn_complete_data
            if payload_session_id:
                completion_emission["session_id"] = payload_session_id
            emissions.append(completion_emission)
        return emissions
