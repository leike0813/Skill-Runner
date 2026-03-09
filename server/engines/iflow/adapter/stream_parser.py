from __future__ import annotations

import re
from typing import TYPE_CHECKING

from server.runtime.adapter.types import LiveParserEmission, RuntimeAssistantMessage, RuntimeStreamParseResult, RuntimeStreamRawRow
from server.runtime.adapter.common.parser_auth_signal_matcher import (
    detect_auth_signal_from_patterns,
)
from server.runtime.protocol.parse_utils import (
    dedup_assistant_messages,
    find_session_id_in_text,
    stream_lines_with_offsets,
    strip_runtime_script_envelope,
)

if TYPE_CHECKING:
    from .execution_adapter import IFlowExecutionAdapter


class IFlowStreamParser:
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
        split_merged = "\n".join([row["line"] for row in [*stdout_rows, *stderr_rows] if row["line"]])
        pty_merged = "\n".join([row["line"] for row in pty_rows if row["line"]])
        merged = "\n".join([row["line"] for row in [*stdout_rows, *stderr_rows, *pty_rows] if row["line"]])
        cleaned_split = self._extract_latest_round_text(split_merged)
        cleaned_pty = self._extract_latest_round_text(pty_merged)
        use_pty_fallback = (not cleaned_split) and bool(cleaned_pty)
        cleaned = cleaned_pty if use_pty_fallback else cleaned_split
        assistant_messages: list[RuntimeAssistantMessage] = []
        raw_rows: list[RuntimeStreamRawRow] = []
        confidence = 0.45

        if cleaned:
            assistant_messages.append({"text": cleaned, "raw_ref": None})
            confidence = 0.65
            if use_pty_fallback:
                diagnostics.append("PTY_FALLBACK_USED")
        else:
            raw_rows.extend(stdout_rows)
            raw_rows.extend(stderr_rows)
            raw_rows.extend(pty_rows)
            diagnostics.append("LOW_CONFIDENCE_PARSE")

        if stdout_rows and stderr_rows:
            diagnostics.append("IFLOW_CHANNEL_DRIFT_OBSERVED")

        auth_signal = detect_auth_signal_from_patterns(
            engine="iflow",
            rules=self._adapter.profile.parser_auth_patterns.rules,
            evidence={
                "engine": "iflow",
                "stdout_text": "\n".join(row["line"] for row in stdout_rows if row["line"]),
                "stderr_text": "\n".join(row["line"] for row in stderr_rows if row["line"]),
                "pty_output": "\n".join(row["line"] for row in pty_rows if row["line"]),
                "combined_text": merged,
                "parser_diagnostics": list(dict.fromkeys(diagnostics)),
                "structured_types": ["iflow.execution_info"],
                "extracted": {},
            },
        )

        result: RuntimeStreamParseResult = {
            "parser": "iflow_text",
            "confidence": confidence,
            "session_id": find_session_id_in_text(merged),
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "raw_rows": raw_rows,
            "diagnostics": list(dict.fromkeys(diagnostics)),
            "structured_types": ["iflow.execution_info"],
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
        for item in parsed.get("assistant_messages", []):
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            emission: LiveParserEmission = {"kind": "assistant_message", "text": text}
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
