from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .signal import auth_detection_result_from_runtime_parse
from .types import AuthDetectionResult


@dataclass
class AuthDetectionService:
    def preload(self) -> None:
        return None

    def detect(
        self,
        *,
        engine: str,
        raw_stdout: str,
        raw_stderr: str,
        pty_output: str = "",
        runtime_parse_result: dict[str, Any] | None = None,
    ) -> AuthDetectionResult:
        _ = raw_stdout
        _ = raw_stderr
        _ = pty_output
        return auth_detection_result_from_runtime_parse(
            engine=engine,
            runtime_parse_result=runtime_parse_result,
        )


auth_detection_service = AuthDetectionService()
