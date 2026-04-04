from __future__ import annotations

import re
from typing import Any

from server.runtime.auth_detection.types import AuthDetectionEvidence


class QwenAuthDetector:
    def build_evidence(
        self,
        *,
        engine: str,
        raw_stdout: str,
        raw_stderr: str,
        pty_output: str,
        runtime_parse_result: dict[str, Any] | None,
    ) -> AuthDetectionEvidence:
        diagnostics = []
        structured_types = []
        if isinstance(runtime_parse_result, dict):
            diagnostics = [str(item) for item in runtime_parse_result.get("diagnostics", []) if isinstance(item, str)]
            structured_types = [str(item) for item in runtime_parse_result.get("structured_types", []) if isinstance(item, str)]

        combined = "\n".join(part for part in [raw_stdout, raw_stderr, pty_output] if part)
        extracted: dict[str, Any] = {
            "auth_error_detected": False,
            "error_id": None,
        }
        for error_id, pattern in (
            ("qwen_oauth_token_expired", r"OAuth.*token.*expired|401.*Unauthorized|invalid.*token"),
            ("qwen_api_key_missing", r"API key is missing|Invalid API key|Missing.*authentication"),
            ("qwen_coding_plan_error", r"Coding Plan.*error|subscription.*expired|quota.*exceeded"),
        ):
            if re.search(pattern, combined, re.IGNORECASE):
                extracted["auth_error_detected"] = True
                extracted["error_id"] = error_id
                break

        return AuthDetectionEvidence(
            engine=engine,
            stdout_text=raw_stdout,
            stderr_text=raw_stderr,
            pty_output=pty_output,
            combined_text=combined,
            parser_diagnostics=diagnostics,
            structured_types=structured_types,
            extracted=extracted,
            evidence_sources=["stdout_text", "stderr_text", "combined"],
        )
