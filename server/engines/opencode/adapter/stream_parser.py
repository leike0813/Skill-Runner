from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from server.runtime.adapter.common.live_stream_parser_common import SemanticOverflowExemptionKind
from server.engines.common.opencode_family.stream_parser import (
    OpenCodeFamilyStreamParserCore,
)
from server.runtime.adapter.types import (
    RuntimeStreamParseResult,
)
from server.runtime.protocol.contracts import LiveStreamParserSession

if TYPE_CHECKING:
    from .execution_adapter import OpencodeExecutionAdapter


class OpencodeStreamParser:
    def __init__(self, adapter: "OpencodeExecutionAdapter") -> None:
        self._adapter = adapter
        self._core = OpenCodeFamilyStreamParserCore(
            engine="opencode",
            parser_name="opencode_ndjson",
            auth_rules=adapter.profile.parser_auth_patterns.rules,
        )

    def classify_ndjson_overflow_exemption(
        self,
        stream: str,
        line_text: str,
    ) -> SemanticOverflowExemptionKind | None:
        return self._core.classify_ndjson_overflow_exemption(stream, line_text)

    def _slice_latest_step_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self._core.slice_latest_step_rows(rows)

    def _extract_text_event(self, payload: dict[str, Any]) -> str | None:
        return self._core.extract_text_event(payload)

    def _is_turn_start(self, payload: dict[str, Any]) -> bool:
        return self._core.is_turn_start(payload)

    def _is_turn_complete(self, payload: dict[str, Any]) -> bool:
        return self._core.is_turn_complete(payload)

    def _extract_turn_complete_data(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        return self._core.extract_turn_complete_data(payload)

    def _extract_process_event(
        self,
        *,
        payload: dict[str, Any],
        row: dict[str, Any],
    ):
        return self._core.extract_process_event(payload=payload, row=row)

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
        return self._core.parse_runtime_stream(
            stdout_raw=stdout_raw,
            stderr_raw=stderr_raw,
            pty_raw=pty_raw,
        )

    def start_live_session(self) -> LiveStreamParserSession:
        return self._core.start_live_session()
