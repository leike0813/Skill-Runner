from __future__ import annotations

from typing import TYPE_CHECKING, Any

from server.engines.common.content_block_mapper import map_content_block
from server.models import AdapterTurnOutcome
from server.runtime.adapter.common.parser_auth_signal_matcher import detect_auth_signal_from_patterns
from server.runtime.adapter.types import RuntimeAssistantMessage, RuntimeProcessEvent, RuntimeStreamParseResult
from server.runtime.protocol.parse_utils import find_session_id

from .stream_framer import CodeBuddyFrame, CodeBuddyStreamFramer

if TYPE_CHECKING:
    from .execution_adapter import CodeBuddyExecutionAdapter


class CodeBuddyStreamParser:
    live_semantic_on_finish_only = True
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

    def _parse_frames(self, frames: list[CodeBuddyFrame], *, stdout: str) -> RuntimeStreamParseResult:
        session_id: str | None = None
        assistant_messages: list[RuntimeAssistantMessage] = []
        process_events: list[RuntimeProcessEvent] = []
        diagnostics: list[str] = []
        raw_rows: list[dict[str, Any]] = []
        structured_types: list[str] = []
        tool_use_by_id: dict[str, dict[str, Any]] = {}
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
            if event_type in {"system.init", "system", "init"} and (event_type == "system.init" or str(payload.get("subtype") or "") == "init"):
                started = True
                continue
            if event_type in {"assistant.thinking", "assistant.text", "assistant.tool_use", "user.tool_result"}:
                payload = {**payload, "content": [{**payload, "type": event_type}]}
                event_type = "assistant" if event_type.startswith("assistant.") else "user"
            if event_type in {"assistant", "user"}:
                started = True
                for block in self._content(payload):
                    mapped = map_content_block(block, raw_ref=raw_ref, tool_use_by_id=tool_use_by_id)
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
        if result_payload is None:
            failed = True
            diagnostics.append("CODEBUDDY_MISSING_TERMINAL_RESULT")
        result: RuntimeStreamParseResult = {"parser": "codebuddy_stream_json", "confidence": 0.95 if completed else 0.8 if started else 0.5, "session_id": session_id, "assistant_messages": assistant_messages, "process_events": process_events, "raw_rows": raw_rows, "diagnostics": list(dict.fromkeys(diagnostics)), "structured_types": list(dict.fromkeys(structured_types)), "turn_started": started, "turn_completed": completed, "turn_failed": failed}
        if session_id:
            result["run_handle"] = {"handle_id": session_id}
        markers: list[dict[str, Any]] = []
        if started:
            markers.append({"marker": "start"})
        if completed:
            markers.append({"marker": "complete", "raw_ref": terminal_ref})
        if failed:
            markers.append(
                {
                    "marker": "failed",
                    "raw_ref": terminal_ref,
                    "data": {
                        "reason": (
                            "CODEBUDDY_TERMINAL_ERROR"
                            if result_payload
                            else "CODEBUDDY_MISSING_TERMINAL_RESULT"
                        )
                    },
                }
            )
        result["turn_markers"] = markers
        profile = getattr(self._adapter, "profile", None)
        auth_patterns = getattr(getattr(profile, "parser_auth_patterns", None), "rules", ())
        auth_signal = detect_auth_signal_from_patterns(
            engine="codebuddy",
            rules=auth_patterns,
            evidence={
                "engine": "codebuddy",
                "stdout_text": stdout,
                "stderr_text": "",
                "combined_text": stdout,
                "parser_diagnostics": result["diagnostics"],
                "structured_types": result["structured_types"],
                "extracted": {},
            },
        )
        if auth_signal is not None:
            result["auth_signal"] = auth_signal
        if result_payload and isinstance(result_payload.get("structured_output"), dict):
            result["structured_payloads"] = [{"type": "structured_output", "stream": "stdout", "details": result_payload["structured_output"], "raw_ref": terminal_ref}]
        return result

    def parse_runtime_stream(self, *, stdout_raw: bytes, stderr_raw: bytes, pty_raw: bytes = b"") -> RuntimeStreamParseResult:
        framer = CodeBuddyStreamFramer()
        frames = framer.feed(stdout_raw.decode("utf-8", errors="replace")) + framer.finish()
        return self._parse_frames(frames, stdout=stdout_raw.decode("utf-8", errors="replace"))

    def parse(self, raw_stdout: str) -> dict[str, object]:
        framer = CodeBuddyStreamFramer()
        runtime = self._parse_frames(framer.feed(raw_stdout) + framer.finish(), stdout=raw_stdout)
        if runtime.get("turn_completed"):
            structured = next(iter(runtime.get("structured_payloads", [])), None)
            final_data = structured.get("details") if isinstance(structured, dict) else {"response": (runtime.get("assistant_messages") or [{}])[-1].get("text", "")}
            return {"turn_result": {"outcome": AdapterTurnOutcome.FINAL.value, "final_data": final_data, "repair_level": "none"}, "structured_payload": final_data if isinstance(final_data, dict) else None}
        reason = "CODEBUDDY_MISSING_TERMINAL_RESULT" if "CODEBUDDY_MISSING_TERMINAL_RESULT" in runtime.get("diagnostics", []) else "CODEBUDDY_TERMINAL_ERROR"
        return {"turn_result": {"outcome": AdapterTurnOutcome.ERROR.value, "failure_reason": reason, "repair_level": "none"}, "structured_payload": None}

    def start_live_session(self) -> "_CodeBuddyLiveSession":
        return _CodeBuddyLiveSession(self)


class _CodeBuddyLiveSession:
    """Buffers only semantic publication; framing stays identical to terminal parsing."""
    def __init__(self, parser: CodeBuddyStreamParser) -> None:
        self._parser = parser
        self._stdout = ""

    def feed(self, *, stream: str, text: str, byte_from: int, byte_to: int) -> list[dict[str, Any]]:
        _ = byte_from, byte_to
        if stream == "stdout":
            self._stdout += text
        return []

    def finish(self, *, exit_code: int, failure_reason: str | None) -> list[dict[str, Any]]:
        _ = exit_code
        runtime = self._parser.parse_runtime_stream(stdout_raw=self._stdout.encode("utf-8"), stderr_raw=b"")
        emissions: list[dict[str, Any]] = []
        handle = runtime.get("run_handle")
        if isinstance(handle, dict) and isinstance(handle.get("handle_id"), str):
            emissions.append({"kind": "run_handle", "handle_id": handle["handle_id"], "raw_ref": handle.get("raw_ref")})
        for marker in runtime.get("turn_markers", []):
            if isinstance(marker, dict):
                emissions.append({"kind": "turn_marker", "marker": marker.get("marker"), "raw_ref": marker.get("raw_ref"), "details": marker.get("data", {})})
        for event in runtime.get("process_events", []):
            if isinstance(event, dict):
                emissions.append({"kind": "process_event", "process_type": event.get("process_type"), "summary": event.get("summary"), "classification": event.get("classification"), "details": event.get("details", {}), "text": event.get("text"), "raw_ref": event.get("raw_ref")})
        for message in runtime.get("assistant_messages", []):
            if isinstance(message, dict):
                emissions.append({"kind": "assistant_message", "text": message.get("text"), "raw_ref": message.get("raw_ref")})
        if runtime.get("turn_completed") and failure_reason is None:
            emissions.append({"kind": "turn_completed"})
        return emissions
