from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from server.models import AdapterTurnResult
from server.models.common import AdapterTurnOutcome
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

if TYPE_CHECKING:
    from .execution_adapter import KiloExecutionAdapter


class KiloStreamParser:
    def __init__(self, adapter: "KiloExecutionAdapter") -> None:
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
        text = self._extract_text_event(payload)
        if isinstance(text, str) and text.strip():
            return "assistant_message"
        return None

    def _extract_text_event(self, payload: dict[str, Any]) -> str | None:
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

    def _is_turn_start(self, payload: dict[str, Any]) -> bool:
        return payload.get("type") == "step_start"

    def _is_turn_complete(self, payload: dict[str, Any]) -> bool:
        return payload.get("type") == "step_finish"

    def _extract_turn_complete_data(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self._is_turn_complete(payload):
            return None
        part = payload.get("part")
        if not isinstance(part, dict):
            return None
        data: dict[str, Any] = {}
        tokens_obj = part.get("tokens")
        if isinstance(tokens_obj, dict):
            data["tokens"] = tokens_obj
        if part.get("cost") is not None:
            data["cost"] = part.get("cost")
        return data or None

    def _extract_error_data(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if payload.get("type") != "error":
            return None
        error_obj = payload.get("error")
        if not isinstance(error_obj, dict):
            return {"message": "Kilo runtime error", "error_name": None}
        data_obj = error_obj.get("data")
        data = data_obj if isinstance(data_obj, dict) else {}
        message = data.get("message")
        if not isinstance(message, str) or not message.strip():
            message = error_obj.get("message")
        if not isinstance(message, str) or not message.strip():
            message = error_obj.get("name")
        status_code = data.get("statusCode")
        response_error_type: str | None = None
        response_body = data.get("responseBody")
        if isinstance(response_body, str):
            try:
                response_payload = json.loads(response_body)
            except json.JSONDecodeError:
                response_payload = None
            if isinstance(response_payload, dict):
                response_error = response_payload.get("error")
                if isinstance(response_error, dict):
                    response_type = response_error.get("type")
                    if isinstance(response_type, str):
                        response_error_type = response_type
        return {
            "message": message if isinstance(message, str) and message.strip() else "Kilo runtime error",
            "error_name": error_obj.get("name"),
            "status_code": status_code,
            "response_error_type": response_error_type,
        }

    def parse(self, raw_stdout: str) -> dict[str, object]:
        rows: list[dict[str, Any]] = []
        for line in raw_stdout.splitlines():
            candidate = line.strip()
            if not candidate:
                continue
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)

        text_parts: list[str] = []
        error_data: dict[str, Any] | None = None
        turn_complete_data: dict[str, Any] | None = None
        session_id: str | None = None
        for payload in rows:
            row_session_id = find_session_id(payload)
            if row_session_id and not session_id:
                session_id = row_session_id
            extracted_error = self._extract_error_data(payload)
            if extracted_error is not None:
                error_data = extracted_error
            text = self._extract_text_event(payload)
            if isinstance(text, str) and text.strip():
                text_parts.append(text)
            extracted_turn_data = self._extract_turn_complete_data(payload)
            if extracted_turn_data is not None:
                turn_complete_data = extracted_turn_data

        if error_data is not None:
            message = str(error_data.get("message") or "Kilo runtime error")
            turn_result = self._adapter._turn_error(  # noqa: SLF001
                message=message,
                failure_reason="KILO_RUNTIME_ERROR",
            )
            return {"turn_result": turn_result.model_dump(), "structured_payload": None}

        content = "".join(text_parts).strip()
        final_data: dict[str, Any] = {"response": content}
        if session_id:
            final_data["session_id"] = session_id
        if isinstance(turn_complete_data, dict):
            final_data["turn_complete_data"] = turn_complete_data
        turn_result = AdapterTurnResult(
            outcome=AdapterTurnOutcome.FINAL,
            final_data=final_data,
        )
        return {
            "turn_result": turn_result.model_dump(),
            "structured_payload": final_data,
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
        stdout_records, raw_rows = collect_json_parse_errors(stdout_rows)
        pty_records, pty_raw_rows = collect_json_parse_errors(pty_rows)

        assistant_messages: list[RuntimeAssistantMessage] = []
        diagnostics: list[str] = []
        structured_types: list[str] = []
        turn_markers: list[RuntimeTurnMarker] = []
        session_id: str | None = None
        turn_started = False
        turn_completed = False
        turn_failed = False
        turn_complete_data: dict[str, Any] | None = None
        turn_failure_data: dict[str, Any] | None = None
        start_ref: RuntimeStreamRawRef | None = None
        complete_ref: RuntimeStreamRawRef | None = None
        failed_ref: RuntimeStreamRawRef | None = None
        run_handle_ref: RuntimeStreamRawRef | None = None
        run_handle_id: str | None = None
        extracted: dict[str, Any] = {
            "error_name": None,
            "status_code": None,
            "message": None,
            "response_error_type": None,
        }

        def _consume(records: list[dict[str, Any]]) -> None:
            nonlocal session_id, turn_started, turn_completed, turn_failed
            nonlocal turn_complete_data, turn_failure_data
            nonlocal start_ref, complete_ref, failed_ref, run_handle_id, run_handle_ref
            for row in records:
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    continue
                row_session_id = find_session_id(payload)
                if row_session_id and not session_id:
                    session_id = row_session_id
                payload_type = payload.get("type")
                if isinstance(payload_type, str):
                    structured_types.append(payload_type)
                raw_ref: RuntimeStreamRawRef = {
                    "stream": str(row["stream"]),
                    "byte_from": int(row["byte_from"]),
                    "byte_to": int(row["byte_to"]),
                }
                if self._is_turn_start(payload) and not turn_started:
                    turn_started = True
                    start_ref = raw_ref
                    if isinstance(row_session_id, str) and row_session_id.strip():
                        run_handle_id = row_session_id.strip()
                        run_handle_ref = raw_ref
                if self._is_turn_complete(payload):
                    turn_completed = True
                    complete_ref = raw_ref
                    data = self._extract_turn_complete_data(payload)
                    if isinstance(data, dict):
                        turn_complete_data = data
                error_data = self._extract_error_data(payload)
                if error_data is not None:
                    turn_failed = True
                    failed_ref = raw_ref
                    turn_failure_data = error_data
                    extracted["error_name"] = error_data.get("error_name")
                    extracted["status_code"] = error_data.get("status_code")
                    extracted["message"] = error_data.get("message")
                    extracted["response_error_type"] = error_data.get("response_error_type")
                text = self._extract_text_event(payload)
                if isinstance(text, str) and text.strip():
                    assistant_messages.append({"text": text, "raw_ref": raw_ref})

        _consume(stdout_records)
        if not assistant_messages and pty_records:
            diagnostics.append("PTY_FALLBACK_USED")
            _consume(pty_records)
        raw_rows.extend(pty_raw_rows)
        if raw_rows:
            diagnostics.append("UNPARSED_CONTENT_FELL_BACK_TO_RAW")

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

        stdout_text = stdout_raw.decode("utf-8", errors="replace")
        stderr_text = stderr_raw.decode("utf-8", errors="replace")
        pty_text = pty_raw.decode("utf-8", errors="replace")
        combined_text = "\n".join(part for part in (stdout_text, stderr_text, pty_text) if part)
        auth_signal = detect_auth_signal_from_patterns(
            engine="kilo",
            rules=self._adapter.profile.parser_auth_patterns.rules,
            evidence={
                "engine": "kilo",
                "stdout_text": stdout_text,
                "stderr_text": stderr_text,
                "pty_output": pty_text,
                "combined_text": combined_text,
                "parser_diagnostics": list(dict.fromkeys(diagnostics)),
                "structured_types": list(dict.fromkeys(structured_types)),
                "provider_id": "kilo",
                "extracted": extracted,
            },
        )
        result: RuntimeStreamParseResult = {
            "parser": "kilo_jsonl",
            "confidence": 0.95 if assistant_messages or turn_failed else 0.6,
            "session_id": session_id,
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "raw_rows": raw_rows,
            "diagnostics": diagnostics,
            "structured_types": list(dict.fromkeys(structured_types)),
            "turn_started": turn_started,
            "turn_completed": turn_completed,
            "turn_failed": turn_failed,
            "turn_markers": turn_markers,
        }
        if isinstance(turn_complete_data, dict):
            result["turn_complete_data"] = turn_complete_data
        if isinstance(turn_failure_data, dict):
            result["turn_failure_data"] = turn_failure_data
        if isinstance(run_handle_id, str) and run_handle_id.strip():
            result["run_handle"] = {"handle_id": run_handle_id, "raw_ref": run_handle_ref}
        if auth_signal is not None:
            result["auth_signal"] = auth_signal
        return result

    def start_live_session(self) -> "_KiloLiveSession":
        return _KiloLiveSession(self)


class _KiloLiveSession(NdjsonLiveStreamParserSession):
    def __init__(self, parser: KiloStreamParser) -> None:
        super().__init__(
            accepted_streams={"stdout", "pty"},
            overflow_exemption_probe=parser.classify_ndjson_overflow_exemption,
        )
        self._parser = parser
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
        _ = stream
        emissions: list[LiveParserEmission] = []
        session_id = find_session_id(payload)
        if self._parser._is_turn_start(payload) and not self._turn_start_emitted:  # noqa: SLF001
            self._turn_start_emitted = True
            emissions.append({"kind": "turn_marker", "marker": "start", "raw_ref": raw_ref})
        if (
            self._parser._is_turn_start(payload)  # noqa: SLF001
            and not self._run_handle_emitted
            and isinstance(session_id, str)
            and session_id.strip()
        ):
            self._run_handle_emitted = True
            emissions.append({"kind": "run_handle", "handle_id": session_id.strip(), "raw_ref": raw_ref})
        if self._parser._is_turn_complete(payload) and not self._turn_complete_emitted:  # noqa: SLF001
            self._turn_complete_emitted = True
            turn_complete_data = self._parser._extract_turn_complete_data(payload)  # noqa: SLF001
            marker: LiveParserEmission = {"kind": "turn_marker", "marker": "complete", "raw_ref": raw_ref}
            if isinstance(turn_complete_data, dict):
                marker["turn_complete_data"] = turn_complete_data
            emissions.append(marker)
            completed: LiveParserEmission = {"kind": "turn_completed"}
            if isinstance(turn_complete_data, dict):
                completed["turn_complete_data"] = turn_complete_data
            emissions.append(completed)
        error_data = self._parser._extract_error_data(payload)  # noqa: SLF001
        if error_data is not None and not self._turn_failed_emitted:
            self._turn_failed_emitted = True
            emissions.append(
                {
                    "kind": "turn_marker",
                    "marker": "failed",
                    "raw_ref": raw_ref,
                    "details": error_data,
                }
            )
        text = self._parser._extract_text_event(payload)  # noqa: SLF001
        if isinstance(text, str) and text.strip():
            emission: LiveParserEmission = {
                "kind": "assistant_message",
                "text": text,
                "raw_ref": raw_ref,
            }
            if session_id:
                emission["session_id"] = session_id
            emissions.append(emission)
        return emissions
