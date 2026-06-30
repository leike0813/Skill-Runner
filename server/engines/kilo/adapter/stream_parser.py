from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from server.models import AdapterTurnResult
from server.models.common import AdapterTurnOutcome
from server.runtime.adapter.common.live_stream_parser_common import SemanticOverflowExemptionKind
from server.engines.common.opencode_family.stream_parser import (
    OpenCodeFamilyStreamParserCore,
)
from server.runtime.adapter.types import (
    RuntimeStreamParseResult,
)
from server.runtime.protocol.contracts import LiveStreamParserSession
from server.runtime.protocol.parse_utils import (
    find_session_id,
)

if TYPE_CHECKING:
    from .execution_adapter import KiloExecutionAdapter


class KiloStreamParser:
    def __init__(self, adapter: "KiloExecutionAdapter") -> None:
        self._adapter = adapter
        self._core = OpenCodeFamilyStreamParserCore(
            engine="kilo",
            parser_name="kilo_jsonl",
            auth_rules=adapter.profile.parser_auth_patterns.rules,
            error_extractor=self._extract_error_data,
            fixed_provider_id="kilo",
            mark_error_rows_failed=True,
        )

    def classify_ndjson_overflow_exemption(
        self,
        stream: str,
        line_text: str,
    ) -> SemanticOverflowExemptionKind | None:
        return self._core.classify_ndjson_overflow_exemption(stream, line_text)

    def _extract_text_event(self, payload: dict[str, Any]) -> str | None:
        return self._core.extract_text_event(payload)

    def _is_turn_start(self, payload: dict[str, Any]) -> bool:
        return self._core.is_turn_start(payload)

    def _is_turn_complete(self, payload: dict[str, Any]) -> bool:
        return self._core.is_turn_complete(payload)

    def _extract_turn_complete_data(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        return self._core.extract_turn_complete_data(payload)

    def _extract_process_event(self, *, payload: dict[str, Any], row: dict[str, Any]):
        return self._core.extract_process_event(payload=payload, row=row)

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
        return self._core.parse_runtime_stream(
            stdout_raw=stdout_raw,
            stderr_raw=stderr_raw,
            pty_raw=pty_raw,
        )

    def start_live_session(self) -> LiveStreamParserSession:
        return self._core.start_live_session()
