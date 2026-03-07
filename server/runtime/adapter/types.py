from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, NotRequired, Optional, TypedDict

from ...models import AdapterTurnResult


class ProcessExecutionResult:
    """Normalized process execution result from adapter subprocess."""

    def __init__(
        self,
        exit_code: int,
        raw_stdout: str,
        raw_stderr: str,
        failure_reason: Optional[str] = None,
        runtime_warnings: Optional[list[dict[str, str]]] = None,
    ) -> None:
        self.exit_code = exit_code
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        self.failure_reason = failure_reason
        self.runtime_warnings = list(runtime_warnings or [])


class RuntimeStreamRawRow(TypedDict):
    stream: str
    line: str
    byte_from: int
    byte_to: int


class RuntimeStreamRawRef(TypedDict):
    stream: str
    byte_from: int
    byte_to: int


class RuntimeAssistantMessage(TypedDict):
    text: str
    raw_ref: NotRequired[RuntimeStreamRawRef | None]


class LiveParserEmission(TypedDict):
    kind: Literal["assistant_message", "diagnostic"]
    text: NotRequired[str]
    code: NotRequired[str]
    raw_ref: NotRequired[RuntimeStreamRawRef | None]
    session_id: NotRequired[str | None]
    structured_type: NotRequired[str | None]


class RuntimeStreamParseResult(TypedDict):
    parser: str
    confidence: float
    session_id: Optional[str]
    assistant_messages: list[RuntimeAssistantMessage]
    raw_rows: list[RuntimeStreamRawRow]
    diagnostics: list[str]
    structured_types: list[str]
    structured_payloads: NotRequired[list[dict[str, Any]]]


class EngineRunResult:
    """
    Standardized payload returned by an adapter execution.
    Contains raw outputs, file paths, and artifact metadata.
    """

    def __init__(
        self,
        exit_code: int,
        raw_stdout: str,
        raw_stderr: str,
        artifacts_created: list[Path] | None = None,
        failure_reason: str | None = None,
        repair_level: str = "none",
        turn_result: AdapterTurnResult | None = None,
        runtime_warnings: list[dict[str, str]] | None = None,
    ) -> None:
        self.exit_code = exit_code
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        self.artifacts_created = artifacts_created or []
        self.failure_reason = failure_reason
        self.repair_level = repair_level
        self.turn_result = turn_result
        self.runtime_warnings = list(runtime_warnings or [])
