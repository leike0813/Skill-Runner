from __future__ import annotations

from typing import Any, Protocol

from .types import AuthDetectionEvidence


class AuthDetector(Protocol):
    def build_evidence(
        self,
        *,
        engine: str,
        raw_stdout: str,
        raw_stderr: str,
        pty_output: str,
        runtime_parse_result: dict[str, Any] | None,
    ) -> AuthDetectionEvidence:
        ...
