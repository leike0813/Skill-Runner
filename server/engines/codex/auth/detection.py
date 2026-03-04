from __future__ import annotations

from typing import Any

from server.runtime.auth_detection.types import AuthDetectionEvidence


class CodexAuthDetector:
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
        return AuthDetectionEvidence(
            engine=engine,
            stdout_text=raw_stdout,
            stderr_text=raw_stderr,
            pty_output=pty_output,
            combined_text=combined,
            parser_diagnostics=diagnostics,
            structured_types=structured_types,
            evidence_sources=["stdout_text", "stderr_text", "combined"],
        )
