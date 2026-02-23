import json
from pathlib import Path
from typing import Any, Dict

from .base import (
    EngineAdapter,
    ProcessExecutionResult,
    RuntimeAssistantMessage,
    RuntimeStreamParseResult,
)
from ..models import AdapterTurnResult, EngineSessionHandle, SkillManifest
from ..services.runtime_parse_utils import (
    collect_json_parse_errors,
    dedup_assistant_messages,
    find_session_id,
    stream_lines_with_offsets,
    strip_runtime_script_envelope,
)


class OpencodeAdapter(EngineAdapter):
    def _capability_unavailable(self) -> RuntimeError:
        return RuntimeError(
            "ENGINE_CAPABILITY_UNAVAILABLE: opencode adapter execute capability is not implemented"
        )

    def _construct_config(self, skill: SkillManifest, run_dir: Path, options: Dict[str, Any]) -> Path:
        raise self._capability_unavailable()

    def _setup_environment(
        self,
        skill: SkillManifest,
        run_dir: Path,
        config_path: Path,
        options: Dict[str, Any],
    ) -> Path:
        raise self._capability_unavailable()

    def _build_prompt(self, skill: SkillManifest, run_dir: Path, input_data: Dict[str, Any]) -> str:
        raise self._capability_unavailable()

    async def _execute_process(
        self,
        prompt: str,
        run_dir: Path,
        skill: SkillManifest,
        options: Dict[str, Any],
    ) -> ProcessExecutionResult:
        raise self._capability_unavailable()

    def _parse_output(self, raw_stdout: str) -> AdapterTurnResult:
        result, repair_level = self._parse_json_with_deterministic_repair(raw_stdout)
        if result is not None:
            return self._build_turn_result_from_payload(result, repair_level)
        return self._turn_error(message="failed to parse opencode output")

    def build_start_command(
        self,
        *,
        prompt: str,
        options: Dict[str, Any],
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        raise self._capability_unavailable()

    def build_resume_command(
        self,
        prompt: str,
        options: Dict[str, Any],
        session_handle: EngineSessionHandle,
        passthrough_args: list[str] | None = None,
        use_profile_defaults: bool = True,
    ) -> list[str]:
        raise self._capability_unavailable()

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
        diagnostics: list[str] = []
        session_id: str | None = None
        structured_types: list[str] = []

        def _consume(parsed_rows: list[dict[str, Any]]) -> None:
            nonlocal session_id
            for row in parsed_rows:
                payload = row["payload"]
                row_session_id = find_session_id(payload)
                if row_session_id and not session_id:
                    session_id = row_session_id
                payload_type = payload.get("type")
                if isinstance(payload_type, str):
                    structured_types.append(payload_type)
                if payload.get("type") != "text":
                    continue
                part = payload.get("part")
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        assistant_messages.append(
                            {
                                "text": text,
                                "raw_ref": {
                                    "stream": row["stream"],
                                    "byte_from": row["byte_from"],
                                    "byte_to": row["byte_to"],
                                },
                            }
                        )

        _consume(records)
        if not assistant_messages and pty_records:
            diagnostics.append("PTY_FALLBACK_USED")
            _consume(pty_records)
        raw_rows.extend(pty_raw_rows)
        if raw_rows:
            diagnostics.append("UNPARSED_CONTENT_FELL_BACK_TO_RAW")
        return {
            "parser": "opencode_ndjson",
            "confidence": 0.95 if assistant_messages else 0.6,
            "session_id": session_id,
            "assistant_messages": dedup_assistant_messages(assistant_messages),
            "raw_rows": raw_rows,
            "diagnostics": diagnostics,
            "structured_types": list(dict.fromkeys(structured_types)),
        }
