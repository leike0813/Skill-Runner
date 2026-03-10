from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Literal, cast

from server.runtime.adapter.types import (
    LiveParserEmission,
    RuntimeAssistantMessage,
    RuntimeStreamParseResult,
    RuntimeStreamRawRef,
    RuntimeStreamRawRow,
    RuntimeTurnMarker,
)
from server.runtime.adapter.common.parser_auth_signal_matcher import (
    detect_auth_signal_from_patterns,
)
from server.runtime.protocol.parse_utils import (
    extract_fenced_or_plain_json,
    dedup_assistant_messages,
    find_session_id_in_text,
    stream_lines_with_offsets,
    strip_runtime_script_envelope,
)

if TYPE_CHECKING:
    from .execution_adapter import IFlowExecutionAdapter


class IFlowStreamParser:
    live_semantic_on_finish_only = True

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
        stdout_text = stdout_raw.decode("utf-8", errors="replace")
        stderr_text = stderr_raw.decode("utf-8", errors="replace")
        pty_text = pty_raw.decode("utf-8", errors="replace")
        merged = "\n".join([row["line"] for row in [*stdout_rows, *stderr_rows, *pty_rows] if row["line"]])
        assistant_messages: list[RuntimeAssistantMessage] = []
        raw_rows: list[RuntimeStreamRawRow] = []
        confidence = 0.45
        run_handle_id: str | None = None
        run_handle_raw_ref: RuntimeStreamRawRef | None = None
        turn_completed = False
        turn_complete_raw_ref: RuntimeStreamRawRef | None = None
        turn_complete_data: dict[str, Any] | None = None
        consumed_ranges: dict[str, list[tuple[int, int]]] = {
            "stdout": [],
            "stderr": [],
            "pty": [],
        }
        session_id: str | None = None
        message_stream: str | None = None
        execution_info_stream: str | None = None

        def _stream_span(stream: str, rows: list[RuntimeStreamRawRow], raw_size: int) -> RuntimeStreamRawRef:
            if rows:
                return {
                    "stream": str(rows[0]["stream"]),
                    "byte_from": int(rows[0]["byte_from"]),
                    "byte_to": int(rows[-1]["byte_to"]),
                }
            return {"stream": stream, "byte_from": 0, "byte_to": max(0, raw_size)}

        def _mark_consumed(stream: str, byte_from: int, byte_to: int) -> None:
            if stream not in consumed_ranges:
                return
            if byte_to <= byte_from:
                return
            consumed_ranges[stream].append((byte_from, byte_to))

        def _extract_execution_info(*, stream: str, text: str) -> tuple[str | None, dict[str, Any] | None, RuntimeStreamRawRef | None]:
            match = re.search(r"<Execution Info>\s*([\s\S]*?)\s*</Execution Info>", text, flags=re.IGNORECASE)
            if match is None:
                return None, None, None
            byte_from = len(text[: match.start()].encode("utf-8", errors="replace"))
            byte_to = len(text[: match.end()].encode("utf-8", errors="replace"))
            inner = (match.group(1) or "").strip()
            payload_obj: Any | None = None
            if inner:
                payload_obj = extract_fenced_or_plain_json(inner)
                if payload_obj is None:
                    try:
                        payload_obj = json.loads(inner)
                    except json.JSONDecodeError:
                        payload_obj = None
            if not isinstance(payload_obj, dict):
                diagnostics.append("IFLOW_EXECUTION_INFO_PARSE_FAILED")
                return None, None, {
                    "stream": stream,
                    "byte_from": max(0, int(byte_from)),
                    "byte_to": max(int(byte_from), int(byte_to)),
                }
            payload = dict(payload_obj)
            session_obj = payload.pop("session-id", None)
            session_value = session_obj.strip() if isinstance(session_obj, str) and session_obj.strip() else None
            return (
                session_value,
                payload,
                {
                    "stream": stream,
                    "byte_from": max(0, int(byte_from)),
                    "byte_to": max(int(byte_from), int(byte_to)),
                },
            )

        def _extract_message_text(text: str) -> str:
            return self._extract_latest_round_text(text)

        message_stdout = _extract_message_text(stdout_text)
        message_stderr = _extract_message_text(stderr_text)
        message_pty = _extract_message_text(pty_text)

        exec_session, exec_payload, exec_raw_ref = _extract_execution_info(stream="stderr", text=stderr_text)
        if exec_raw_ref is None:
            exec_session, exec_payload, exec_raw_ref = _extract_execution_info(stream="stdout", text=stdout_text)
            if exec_raw_ref is not None:
                execution_info_stream = "stdout"
                diagnostics.append("IFLOW_CHANNEL_DRIFT_OBSERVED")
                diagnostics.append("IFLOW_EXECUTION_INFO_CHANNEL_DRIFT_CORRECTED")
        else:
            execution_info_stream = "stderr"
        if exec_raw_ref is None:
            exec_session, exec_payload, exec_raw_ref = _extract_execution_info(stream="pty", text=pty_text)
            if exec_raw_ref is not None:
                execution_info_stream = "pty"
                diagnostics.append("PTY_FALLBACK_USED")
                diagnostics.append("IFLOW_CHANNEL_DRIFT_OBSERVED")
                diagnostics.append("IFLOW_EXECUTION_INFO_CHANNEL_DRIFT_CORRECTED")

        if exec_raw_ref is not None:
            turn_completed = True
            turn_complete_raw_ref = exec_raw_ref
            if isinstance(exec_payload, dict):
                turn_complete_data = dict(exec_payload)
            if exec_session:
                run_handle_id = exec_session
                session_id = exec_session
                run_handle_raw_ref = exec_raw_ref
            _mark_consumed(exec_raw_ref["stream"], int(exec_raw_ref["byte_from"]), int(exec_raw_ref["byte_to"]))

        message_text = ""
        message_raw_ref: RuntimeStreamRawRef | None = None
        if message_stdout:
            message_text = message_stdout
            message_stream = "stdout"
            message_raw_ref = _stream_span("stdout", cast(list[RuntimeStreamRawRow], stdout_rows), len(stdout_raw))
        elif message_stderr:
            message_text = message_stderr
            message_stream = "stderr"
            message_raw_ref = _stream_span("stderr", cast(list[RuntimeStreamRawRow], stderr_rows), len(stderr_raw))
            diagnostics.append("IFLOW_CHANNEL_DRIFT_OBSERVED")
            diagnostics.append("IFLOW_MESSAGE_CHANNEL_DRIFT_CORRECTED")
        elif message_pty:
            message_text = message_pty
            message_stream = "pty"
            message_raw_ref = _stream_span("pty", cast(list[RuntimeStreamRawRow], pty_rows), len(pty_raw))
            diagnostics.append("PTY_FALLBACK_USED")

        if message_text and message_raw_ref is not None:
            assistant_messages.append({"text": message_text, "raw_ref": message_raw_ref})
            _mark_consumed(
                message_raw_ref["stream"],
                int(message_raw_ref["byte_from"]),
                int(message_raw_ref["byte_to"]),
            )
            confidence = 0.72

        if session_id is None:
            session_id = (
                find_session_id_in_text(stderr_text)
                or find_session_id_in_text(stdout_text)
                or find_session_id_in_text(pty_text)
            )
        if run_handle_id is None and session_id:
            run_handle_id = session_id
            run_handle_raw_ref = None

        def _row_overlaps_consumed(row: RuntimeStreamRawRow) -> bool:
            ranges = consumed_ranges.get(str(row["stream"]), [])
            if not ranges:
                return False
            row_start = int(row["byte_from"])
            row_end = int(row["byte_to"])
            for start, end in ranges:
                if row_start < end and row_end > start:
                    return True
            return False

        raw_candidates: list[RuntimeStreamRawRow] = [
            *cast(list[RuntimeStreamRawRow], stdout_rows),
            *cast(list[RuntimeStreamRawRow], stderr_rows),
            *cast(list[RuntimeStreamRawRow], pty_rows),
        ]
        raw_rows = [row for row in raw_candidates if not _row_overlaps_consumed(row)]
        if not assistant_messages and not turn_completed:
            diagnostics.append("LOW_CONFIDENCE_PARSE")
        if raw_rows:
            diagnostics.append("UNPARSED_CONTENT_FELL_BACK_TO_RAW")

        auth_signal = detect_auth_signal_from_patterns(
            engine="iflow",
            rules=self._adapter.profile.parser_auth_patterns.rules,
            evidence={
                "engine": "iflow",
                "stdout_text": stdout_text,
                "stderr_text": stderr_text,
                "pty_output": pty_text,
                "combined_text": merged,
                "parser_diagnostics": list(dict.fromkeys(diagnostics)),
                "structured_types": ["iflow.execution_info"],
                "extracted": {
                    "message_stream": message_stream,
                    "execution_info_stream": execution_info_stream,
                },
            },
        )

        turn_markers: list[RuntimeTurnMarker] = [{"marker": "start", "raw_ref": None}]
        if turn_completed:
            complete_marker: RuntimeTurnMarker = {
                "marker": "complete",
                "raw_ref": turn_complete_raw_ref,
            }
            if isinstance(turn_complete_data, dict):
                complete_marker["data"] = turn_complete_data
            turn_markers.append(complete_marker)

        result: RuntimeStreamParseResult = {
            "parser": "iflow_text",
            "confidence": confidence,
            "session_id": session_id,
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "turn_started": True,
            "turn_completed": turn_completed,
            "turn_markers": turn_markers,
            "raw_rows": raw_rows,
            "diagnostics": list(dict.fromkeys(diagnostics)),
            "structured_types": ["iflow.execution_info"],
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

    def start_live_session(self) -> "_IFlowLiveSession":
        return _IFlowLiveSession(self)


class _IFlowLiveSession:
    def __init__(self, parser: IFlowStreamParser) -> None:
        self._parser = parser
        self._stdout = bytearray()
        self._stderr = bytearray()
        self._pty = bytearray()

    def feed(
        self,
        *,
        stream: str,
        text: str,
        byte_from: int,
        byte_to: int,
    ) -> list[LiveParserEmission]:
        _ = byte_from
        _ = byte_to
        encoded = text.encode("utf-8", errors="replace")
        if stream == "stderr":
            self._stderr.extend(encoded)
        elif stream == "pty":
            self._pty.extend(encoded)
        else:
            self._stdout.extend(encoded)
        return []

    def finish(
        self,
        *,
        exit_code: int,
        failure_reason: str | None,
    ) -> list[LiveParserEmission]:
        _ = exit_code
        _ = failure_reason
        parsed = self._parser.parse_runtime_stream(
            stdout_raw=bytes(self._stdout),
            stderr_raw=bytes(self._stderr),
            pty_raw=bytes(self._pty),
        )
        emissions: list[LiveParserEmission] = []
        session_id = parsed.get("session_id")
        parsed_turn_complete_data = (
            parsed.get("turn_complete_data")
            if isinstance(parsed.get("turn_complete_data"), dict)
            else None
        )
        run_handle_obj = parsed.get("run_handle")
        if isinstance(run_handle_obj, dict):
            handle_id_obj = run_handle_obj.get("handle_id")
            if isinstance(handle_id_obj, str) and handle_id_obj.strip():
                run_handle_emission: LiveParserEmission = {
                    "kind": "run_handle",
                    "handle_id": handle_id_obj.strip(),
                }
                raw_ref_obj = run_handle_obj.get("raw_ref")
                if isinstance(raw_ref_obj, dict):
                    run_handle_emission["raw_ref"] = raw_ref_obj
                if isinstance(session_id, str) and session_id:
                    run_handle_emission["session_id"] = session_id
                emissions.append(run_handle_emission)
        turn_markers_obj = parsed.get("turn_markers")
        if isinstance(turn_markers_obj, list):
            for marker_item in turn_markers_obj:
                if not isinstance(marker_item, dict):
                    continue
                marker_obj = marker_item.get("marker")
                marker = marker_obj if isinstance(marker_obj, str) else None
                if marker not in {"start", "complete"}:
                    continue
                marker_literal: Literal["start", "complete"] = cast(Literal["start", "complete"], marker)
                marker_emission: LiveParserEmission = {
                    "kind": "turn_marker",
                    "marker": marker_literal,
                }
                raw_ref_obj = marker_item.get("raw_ref")
                if isinstance(raw_ref_obj, dict):
                    marker_emission["raw_ref"] = raw_ref_obj
                if marker == "complete":
                    marker_data_obj = marker_item.get("data")
                    if isinstance(marker_data_obj, dict):
                        marker_emission["turn_complete_data"] = marker_data_obj
                    elif isinstance(parsed_turn_complete_data, dict):
                        marker_emission["turn_complete_data"] = parsed_turn_complete_data
                if isinstance(session_id, str) and session_id:
                    marker_emission["session_id"] = session_id
                emissions.append(marker_emission)
        if bool(parsed.get("turn_completed")):
            completion_emission: LiveParserEmission = {"kind": "turn_completed"}
            if isinstance(parsed_turn_complete_data, dict):
                completion_emission["turn_complete_data"] = parsed_turn_complete_data
            if isinstance(session_id, str) and session_id:
                completion_emission["session_id"] = session_id
            emissions.append(completion_emission)
        for item in parsed.get("assistant_messages", []):
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            emission: LiveParserEmission = {"kind": "assistant_message", "text": text}
            raw_ref_obj = item.get("raw_ref")
            if isinstance(raw_ref_obj, dict):
                emission["raw_ref"] = raw_ref_obj
            if isinstance(session_id, str) and session_id:
                emission["session_id"] = session_id
            emissions.append(emission)
        for code in parsed.get("diagnostics", []):
            if not isinstance(code, str) or not code:
                continue
            diagnostic_emission: LiveParserEmission = {"kind": "diagnostic", "code": code}
            if isinstance(session_id, str) and session_id:
                diagnostic_emission["session_id"] = session_id
            emissions.append(diagnostic_emission)
        return emissions
