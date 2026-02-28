from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from ...models import EngineSessionHandle, SkillManifest


@dataclass(frozen=True)
class AdapterExecutionContext:
    skill: SkillManifest
    run_dir: Path
    input_data: dict[str, Any]
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterExecutionArtifacts:
    exit_code: int
    raw_stdout: str
    raw_stderr: str
    repair_level: str = "none"
    failure_reason: str | None = None
    session_handle: EngineSessionHandle | None = None
    structured_payload: dict[str, Any] | None = None


class ConfigComposer(Protocol):
    def compose(self, ctx: AdapterExecutionContext) -> Path:
        ...


class WorkspaceProvisioner(Protocol):
    def prepare(self, ctx: AdapterExecutionContext, config_path: Path) -> Path:
        ...


class PromptBuilder(Protocol):
    def render(self, ctx: AdapterExecutionContext) -> str:
        ...


class CommandBuilder(Protocol):
    def build_start(self, ctx: AdapterExecutionContext, prompt: str) -> list[str]:
        ...

    def build_resume(
        self,
        ctx: AdapterExecutionContext,
        prompt: str,
        session_handle: EngineSessionHandle,
    ) -> list[str]:
        ...


class StreamParser(Protocol):
    def parse(self, raw_stdout: str) -> dict[str, Any]:
        ...


class SessionHandleCodec(Protocol):
    def extract(self, raw_stdout: str, turn_index: int) -> EngineSessionHandle:
        ...
