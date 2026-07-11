from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from server.engines.common.content_block_mapper import map_content_block
from server.models import AdapterTurnOutcome
from server.runtime.adapter.common.parser_auth_signal_matcher import detect_auth_signal_from_patterns
from server.runtime.adapter.types import (
    LiveParserEmission,
    RuntimeAssistantMessage,
    RuntimeProcessEvent,
    RuntimeStreamParseResult,
    RuntimeStreamRawRef,
)
from server.runtime.protocol.parse_utils import find_session_id

from .stream_framer import CodeBuddyFrame, CodeBuddyStreamFramer

if TYPE_CHECKING:
    from .execution_adapter import CodeBuddyExecutionAdapter


class CodeBuddyStreamParser:
    def __init__(self, adapter: "CodeBuddyExecutionAdapter") -> None:
        self._adapter = adapter

    @staticmethod
    def _type(payload: dict[str, Any]) -> str:
        return str(payload.get("type") or payload.get("event") or "").lower()

    @staticmethod
    def _content(payload: dict[str, Any]) -> list[dict[str, Any]]:
        content = payload.get("content")
        if not isinstance(content, list):
            message = payload.get("message")
            content = message.get("content") if isinstance(message, dict) else None
        return [item for item in content if isinstance(item, dict)] if isinstance(content, list) else []

    def _parse_frames(
        self,
        frames: list[CodeBuddyFrame],
        *,
        stdout: str,
        stderr: str = "",
        finalize: bool = True,
        tool_use_by_id: dict[str, dict[str, Any]] | None = None,
    ) -> RuntimeStreamParseResult:
        session_id: str | None = None
        session_raw_ref: RuntimeStreamRawRef | None = None
        assistant_messages: list[RuntimeAssistantMessage] = []
        process_events: list[RuntimeProcessEvent] = []
        diagnostics: list[str] = []
        raw_rows: list[dict[str, Any]] = []
        structured_types: list[str] = []
        effective_tool_use_by_id = tool_use_by_id if tool_use_by_id is not None else {}
        started = False
        completed = False
        failed = False
        result_payload: dict[str, Any] | None = None
        terminal_ref: dict[str, Any] | None = None
        for frame in frames:
            raw_ref = {"stream": "stdout", "byte_from": frame.byte_from, "byte_to": frame.byte_to}
            if frame.payload is None:
                diagnostics.append(frame.diagnostic or "CODEBUDDY_FRAME_MALFORMED")
                raw_rows.append({"stream": "stdout", "line": frame.raw, "byte_from": frame.byte_from, "byte_to": frame.byte_to})
                continue
            payload = frame.payload
            event_type = self._type(payload)
            structured_types.append(event_type)
            discovered = find_session_id(payload) or payload.get("session_id")
            if isinstance(discovered, str) and discovered.strip() and session_id is None:
                session_id = discovered.strip()
                session_raw_ref = raw_ref
            if event_type in {"system.init", "system", "init"} and (event_type == "system.init" or str(payload.get("subtype") or "") == "init"):
                started = True
                continue
            if event_type in {"assistant.thinking", "assistant.text", "assistant.tool_use", "user.tool_result"}:
                payload = {**payload, "content": [{**payload, "type": event_type}]}
                event_type = "assistant" if event_type.startswith("assistant.") else "user"
            if event_type in {"assistant", "user"}:
                started = True
                for block in self._content(payload):
                    mapped = map_content_block(
                        block,
                        raw_ref=raw_ref,
                        tool_use_by_id=effective_tool_use_by_id,
                    )
                    if mapped is None:
                        continue
                    if "process_type" in mapped:
                        process_events.append(mapped)  # type: ignore[arg-type]
                    else:
                        assistant_messages.append(mapped)  # type: ignore[arg-type]
                continue
            if event_type == "result":
                started = True
                result_payload = payload
                terminal_ref = raw_ref
                subtype = str(payload.get("subtype") or payload.get("status") or "").lower()
                failed = bool(payload.get("is_error")) or subtype not in {"success", "completed", "complete"}
                completed = not failed
                result_text = payload.get("result")
                if isinstance(result_text, str) and result_text.strip():
                    assistant_messages.append({"text": result_text, "raw_ref": raw_ref})
                continue
            raw_rows.append({"stream": "stdout", "line": frame.raw, "byte_from": frame.byte_from, "byte_to": frame.byte_to})
        if result_payload is None and finalize:
            failed = True
            diagnostics.append("CODEBUDDY_MISSING_TERMINAL_RESULT")
        result: RuntimeStreamParseResult = {"parser": "codebuddy_stream_json", "confidence": 0.95 if completed else 0.8 if started else 0.5, "session_id": session_id, "assistant_messages": assistant_messages, "process_events": process_events, "raw_rows": raw_rows, "diagnostics": list(dict.fromkeys(diagnostics)), "structured_types": list(dict.fromkeys(structured_types)), "turn_started": started, "turn_completed": completed, "turn_failed": failed}
        if session_id:
            result["run_handle"] = {
                "handle_id": session_id,
                "raw_ref": session_raw_ref,
            }
        markers: list[dict[str, Any]] = []
        if started:
            markers.append({"marker": "start"})
        if completed:
            markers.append({"marker": "complete", "raw_ref": terminal_ref})
        if failed:
            failure_code = (
                "CODEBUDDY_TERMINAL_ERROR"
                if result_payload
                else "CODEBUDDY_MISSING_TERMINAL_RESULT"
            )
            failure_message = (
                "CodeBuddy terminal result reported failure"
                if result_payload
                else "CodeBuddy stream ended without a terminal result"
            )
            failure_data = {
                "message": failure_message,
                "code": failure_code,
                "source_type": "type:result",
                "pattern_kind": "codebuddy_terminal_error",
                "fatal": True,
                "status": "failed",
            }
            markers.append(
                {
                    "marker": "failed",
                    "raw_ref": terminal_ref,
                    "data": failure_data,
                }
            )
            result["turn_failure_data"] = failure_data
        result["turn_markers"] = markers
        profile = getattr(self._adapter, "profile", None)
        auth_patterns = getattr(getattr(profile, "parser_auth_patterns", None), "rules", ())
        auth_signal = detect_auth_signal_from_patterns(
            engine="codebuddy",
            rules=auth_patterns,
            evidence={
                "engine": "codebuddy",
                "stdout_text": stdout,
                "stderr_text": stderr,
                "combined_text": "\n".join(part for part in (stdout, stderr) if part),
                "parser_diagnostics": result["diagnostics"],
                "structured_types": result["structured_types"],
                "extracted": {},
            },
        )
        if auth_signal is not None:
            result["auth_signal"] = auth_signal
        if result_payload and isinstance(result_payload.get("structured_output"), dict):
            structured_text = json.dumps(result_payload["structured_output"], ensure_ascii=False)
            assistant_messages.append(
                {
                    "text": structured_text,
                    "raw_ref": terminal_ref,
                    "details": {"source": "structured_output_result"},
                }
            )
        return result

    def parse_runtime_stream(self, *, stdout_raw: bytes, stderr_raw: bytes, pty_raw: bytes = b"") -> RuntimeStreamParseResult:
        _ = pty_raw
        stdout = stdout_raw.decode("utf-8", errors="replace")
        stderr = stderr_raw.decode("utf-8", errors="replace")
        framer = CodeBuddyStreamFramer()
        frames = framer.feed(stdout) + framer.finish()
        return self._parse_frames(frames, stdout=stdout, stderr=stderr)

    def parse(self, raw_stdout: str) -> dict[str, object]:
        framer = CodeBuddyStreamFramer()
        runtime = self._parse_frames(framer.feed(raw_stdout) + framer.finish(), stdout=raw_stdout)
        if runtime.get("turn_completed"):
            terminal = next(
                (
                    item
                    for item in (runtime.get("assistant_messages") or [])
                    if isinstance(item, dict)
                    and isinstance(item.get("details"), dict)
                    and item["details"].get("source") == "structured_output_result"
                ),
                None,
            )
            if isinstance(terminal, dict) and isinstance(terminal.get("text"), str):
                try:
                    final_data = json.loads(terminal["text"])
                except json.JSONDecodeError:
                    final_data = {"response": terminal["text"]}
            else:
                final_data = {"response": (runtime.get("assistant_messages") or [{}])[-1].get("text", "")}
            return {"turn_result": {"outcome": AdapterTurnOutcome.FINAL.value, "final_data": final_data, "repair_level": "none"}, "structured_payload": final_data if isinstance(final_data, dict) else None}
        reason = "CODEBUDDY_MISSING_TERMINAL_RESULT" if "CODEBUDDY_MISSING_TERMINAL_RESULT" in runtime.get("diagnostics", []) else "CODEBUDDY_TERMINAL_ERROR"
        return {"turn_result": {"outcome": AdapterTurnOutcome.ERROR.value, "failure_reason": reason, "repair_level": "none"}, "structured_payload": None}

    def start_live_session(self) -> "_CodeBuddyLiveSession":
        return _CodeBuddyLiveSession(self)


class _CodeBuddyLiveSession:
    """Incrementally publishes complete CodeBuddy frames with persistent semantic state."""

    def __init__(self, parser: CodeBuddyStreamParser) -> None:
        self._parser = parser
        self._framer = CodeBuddyStreamFramer()
        self._tool_use_by_id: dict[str, dict[str, Any]] = {}
        self._last_handle_id: str | None = None
        self._turn_started = False
        self._terminal_seen = False

    def feed(
        self,
        *,
        stream: str,
        text: str,
        byte_from: int,
        byte_to: int,
    ) -> list[LiveParserEmission]:
        _ = byte_from, byte_to
        if stream != "stdout":
            return []
        frames = self._framer.feed(text)
        if not frames:
            return []
        runtime = self._parser._parse_frames(  # noqa: SLF001
            frames,
            stdout=text,
            finalize=False,
            tool_use_by_id=self._tool_use_by_id,
        )
        return self._build_emissions(runtime)

    def finish(
        self,
        *,
        exit_code: int,
        failure_reason: str | None,
    ) -> list[LiveParserEmission]:
        _ = exit_code
        runtime = self._parser._parse_frames(  # noqa: SLF001
            self._framer.finish(),
            stdout="",
            finalize=not self._terminal_seen and failure_reason is None,
            tool_use_by_id=self._tool_use_by_id,
        )
        return self._build_emissions(runtime)

    def _build_emissions(
        self,
        runtime: RuntimeStreamParseResult,
    ) -> list[LiveParserEmission]:
        emissions: list[LiveParserEmission] = []
        handle = runtime.get("run_handle")
        if isinstance(handle, dict):
            handle_id = handle.get("handle_id")
            if isinstance(handle_id, str) and handle_id and handle_id != self._last_handle_id:
                self._last_handle_id = handle_id
                handle_emission: LiveParserEmission = {
                    "kind": "run_handle",
                    "handle_id": handle_id,
                }
                raw_ref = handle.get("raw_ref")
                if isinstance(raw_ref, dict):
                    handle_emission["raw_ref"] = raw_ref
                emissions.append(handle_emission)

        if runtime.get("turn_started") and not self._turn_started:
            self._turn_started = True
            emissions.append({"kind": "turn_marker", "marker": "start"})

        for event in runtime.get("process_events", []):
            if isinstance(event, dict):
                emissions.append(
                    {
                        "kind": "process_event",
                        "process_type": event.get("process_type"),
                        "summary": event.get("summary"),
                        "classification": event.get("classification"),
                        "details": event.get("details", {}),
                        "text": event.get("text"),
                        "raw_ref": event.get("raw_ref"),
                    }
                )
        for message in runtime.get("assistant_messages", []):
            if isinstance(message, dict):
                assistant_emission: LiveParserEmission = {
                    "kind": "assistant_message",
                    "text": message.get("text"),
                    "raw_ref": message.get("raw_ref"),
                }
                details = message.get("details")
                if isinstance(details, dict):
                    assistant_emission["details"] = details
                emissions.append(assistant_emission)

        for code in runtime.get("diagnostics", []):
            if isinstance(code, str) and code:
                emissions.append({"kind": "diagnostic", "code": code})

        if runtime.get("turn_completed") and not self._terminal_seen:
            self._terminal_seen = True
            terminal_marker = self._terminal_marker(runtime, marker="complete")
            emissions.append(terminal_marker)
            emissions.append({"kind": "turn_completed"})
        elif runtime.get("turn_failed") and not self._terminal_seen:
            self._terminal_seen = True
            terminal_marker = self._terminal_marker(runtime, marker="failed")
            emissions.append(terminal_marker)
        return emissions

    @staticmethod
    def _terminal_marker(
        runtime: RuntimeStreamParseResult,
        *,
        marker: str,
    ) -> LiveParserEmission:
        emission: LiveParserEmission = {
            "kind": "turn_marker",
            "marker": marker,
        }
        for item in runtime.get("turn_markers", []):
            if not isinstance(item, dict) or item.get("marker") != marker:
                continue
            raw_ref = item.get("raw_ref")
            if isinstance(raw_ref, dict):
                emission["raw_ref"] = raw_ref
            details = item.get("data")
            if marker == "failed" and isinstance(details, dict):
                emission["details"] = details
            break
        return emission
