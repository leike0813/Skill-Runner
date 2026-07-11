from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from server.runtime.adapter.common.profile_loader import AdapterProfile
from server.services.engine_management.agent_cli_manager import AgentCliManager


class UiShellLaunchValidationError(ValueError):
    pass


@dataclass(frozen=True)
class UiShellLaunchPlan:
    args: tuple[str, ...]
    env: dict[str, str]
    provider_id: str | None = None


class UiShellLaunchHandler(Protocol):
    def validate(self, provider_id: str | None) -> str | None:
        ...

    def prepare(
        self,
        *,
        session_dir: Path,
        base_env: dict[str, str],
        launch_args: tuple[str, ...],
        provider_id: str | None,
        agent_manager: AgentCliManager,
    ) -> UiShellLaunchPlan:
        ...


class DefaultUiShellLaunchHandler:
    def validate(self, provider_id: str | None) -> str | None:
        if isinstance(provider_id, str) and provider_id.strip():
            raise UiShellLaunchValidationError(
                "provider_id is supported only by provider-aware UI-shell engines"
            )
        return None

    def prepare(
        self,
        *,
        session_dir: Path,
        base_env: dict[str, str],
        launch_args: tuple[str, ...],
        provider_id: str | None,
        agent_manager: AgentCliManager,
    ) -> UiShellLaunchPlan:
        _ = session_dir, agent_manager
        self.validate(provider_id)
        return UiShellLaunchPlan(args=launch_args, env=dict(base_env))


def resolve_ui_shell_launch_handler(
    engine: str,
    profile: AdapterProfile,
) -> UiShellLaunchHandler:
    if engine == "codebuddy":
        from server.engines.codebuddy.ui_shell_launch_handler import CodeBuddyUiShellLaunchHandler

        return CodeBuddyUiShellLaunchHandler(profile)
    return DefaultUiShellLaunchHandler()
