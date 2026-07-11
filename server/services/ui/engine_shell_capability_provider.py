from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Protocol

from server.config import config
from server.runtime.adapter.common.profile_loader import AdapterProfile, load_adapter_profile
from server.services.engine_management.agent_cli_manager import AgentCliManager
from server.services.engine_management.engine_catalog import supported_engines
from server.services.ui.ui_shell_session_config import ProfiledJsonSessionSecurity
from server.services.ui.ui_shell_launch_handler import (
    UiShellLaunchHandler,
    resolve_ui_shell_launch_handler,
)


class SandboxProbeStrategy(Protocol):
    def probe(self, *, agent_manager: AgentCliManager, engine: str) -> tuple[str, str]:
        ...


class SessionSecurityStrategy(Protocol):
    def prepare(
        self,
        *,
        session_dir: Path,
        env: Dict[str, str],
        sandbox_enabled: bool,
        custom_model: str | None = None,
    ) -> None:
        ...


class AuthHintStrategy(Protocol):
    def apply(
        self,
        *,
        agent_manager: AgentCliManager,
        sandbox_enabled: bool,
        sandbox_status: str,
        sandbox_message: str,
    ) -> tuple[bool, str, str]:
        ...


@dataclass(frozen=True)
class EngineShellCapability:
    command_id: str
    label: str
    engine: str
    launch_args: tuple[str, ...]
    trust_bootstrap_parent: bool
    sandbox_arg: str | None
    retry_without_sandbox_on_early_exit: bool
    sandbox_probe_strategy: SandboxProbeStrategy
    session_security_strategy: SessionSecurityStrategy
    auth_hint_strategy: AuthHintStrategy
    launch_handler: UiShellLaunchHandler


@dataclass(frozen=True)
class _StaticUnsupportedSandboxProbe:
    message: str

    def probe(self, *, agent_manager: AgentCliManager, engine: str) -> tuple[str, str]:
        _ = (agent_manager, engine)
        return ("unsupported", self.message)


@dataclass(frozen=True)
class _StaticSupportedSandboxProbe:
    message: str

    def probe(self, *, agent_manager: AgentCliManager, engine: str) -> tuple[str, str]:
        _ = (agent_manager, engine)
        return ("supported", self.message)


class _CodexSandboxProbe:
    def probe(self, *, agent_manager: AgentCliManager, engine: str) -> tuple[str, str]:
        _ = (agent_manager, engine)
        if os.environ.get("LANDLOCK_ENABLED") == "0":
            return (
                "unsupported",
                "LANDLOCK is disabled in current environment; codex inline TUI runs without enforced sandbox.",
            )
        return ("supported", "LANDLOCK enabled.")


class _NoopSecurity:
    def prepare(
        self,
        *,
        session_dir: Path,
        env: Dict[str, str],
        sandbox_enabled: bool,
        custom_model: str | None = None,
    ) -> None:
        _ = (session_dir, env, sandbox_enabled, custom_model)


class _NoopAuthHint:
    def apply(
        self,
        *,
        agent_manager: AgentCliManager,
        sandbox_enabled: bool,
        sandbox_status: str,
        sandbox_message: str,
    ) -> tuple[bool, str, str]:
        _ = agent_manager
        return (sandbox_enabled, sandbox_status, sandbox_message)


class EngineShellCapabilityProvider:
    def __init__(self) -> None:
        self._capabilities = self._build_capabilities()

    def _adapter_profile_path(self, engine: str) -> Path:
        return Path(config.SYSTEM.ROOT) / "server" / "engines" / engine / "adapter" / "adapter_profile.json"

    def _resolve_launch_args(self, engine: str) -> tuple[str, ...]:
        profile = load_adapter_profile(engine, self._adapter_profile_path(engine))
        return tuple(profile.resolve_command_defaults(action="ui_shell"))

    def _load_profile(self, engine: str) -> AdapterProfile:
        return load_adapter_profile(engine, self._adapter_profile_path(engine))

    def _resolve_sandbox_probe_strategy(self, profile: AdapterProfile) -> SandboxProbeStrategy:
        strategy = profile.ui_shell.sandbox_probe_strategy
        message = profile.ui_shell.sandbox_probe_message or "Sandbox capability is unknown for this engine."
        if strategy == "codex_landlock":
            return _CodexSandboxProbe()
        if strategy == "static_supported":
            return _StaticSupportedSandboxProbe(message=message)
        return _StaticUnsupportedSandboxProbe(message=message)

    def _resolve_auth_hint_strategy(self, profile: AdapterProfile) -> AuthHintStrategy:
        return _NoopAuthHint()

    def _resolve_session_security_strategy(self, profile: AdapterProfile) -> SessionSecurityStrategy:
        if profile.resolve_ui_shell_target_relpath() is None:
            return _NoopSecurity()
        return ProfiledJsonSessionSecurity(profile)

    def _build_capability(self, engine: str) -> EngineShellCapability | None:
        profile = self._load_profile(engine)
        if not profile.ui_shell.enabled:
            return None
        return EngineShellCapability(
            command_id=profile.ui_shell.command_id,
            label=profile.ui_shell.label,
            engine=engine,
            launch_args=tuple(profile.resolve_command_defaults(action="ui_shell")),
            trust_bootstrap_parent=profile.ui_shell.trust_bootstrap_parent,
            sandbox_arg=profile.ui_shell.sandbox_arg,
            retry_without_sandbox_on_early_exit=profile.ui_shell.retry_without_sandbox_on_early_exit,
            sandbox_probe_strategy=self._resolve_sandbox_probe_strategy(profile),
            session_security_strategy=self._resolve_session_security_strategy(profile),
            auth_hint_strategy=self._resolve_auth_hint_strategy(profile),
            launch_handler=resolve_ui_shell_launch_handler(engine, profile),
        )

    def _build_capabilities(self) -> dict[str, EngineShellCapability]:
        capabilities: dict[str, EngineShellCapability] = {}
        for engine in supported_engines():
            capability = self._build_capability(engine)
            if capability is not None:
                capabilities[engine] = capability
        return capabilities

    def get(self, engine: str) -> EngineShellCapability | None:
        return self._capabilities.get(engine.strip().lower())

    def list_capabilities(self) -> tuple[EngineShellCapability, ...]:
        return tuple(self._capabilities.values())
