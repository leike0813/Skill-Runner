from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Protocol

from server.config import config
from server.runtime.adapter.common.profile_loader import AdapterProfile, load_adapter_profile
from server.services.engine_management.agent_cli_manager import AgentCliManager
from server.services.engine_management.engine_catalog import supported_engines
from server.services.ui.ui_shell_session_config import ProfiledJsonSessionSecurity


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


class _GeminiSandboxProbe:
    def probe(self, *, agent_manager: AgentCliManager, engine: str) -> tuple[str, str]:
        env = agent_manager.profile.build_subprocess_env(os.environ.copy())
        path_env = env.get("PATH", os.environ.get("PATH", ""))
        runtime_errors: list[str] = []
        for runtime in ("docker", "podman"):
            runtime_path = shutil.which(runtime, path=path_env)
            if not runtime_path:
                continue
            try:
                result = subprocess.run(
                    [runtime_path, "info"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=3,
                )
            except (OSError, subprocess.SubprocessError, TypeError, ValueError) as exc:
                runtime_errors.append(f"{runtime}: {str(exc)}")
                continue
            if result.returncode == 0:
                return (
                    "supported",
                    f"{engine} sandbox runtime is available via {runtime}.",
                )
            first_line = ((result.stderr or "").strip() or (result.stdout or "").strip()).splitlines()
            detail = first_line[0] if first_line else f"exit={result.returncode}"
            runtime_errors.append(f"{runtime}: {detail}")
        if runtime_errors:
            return (
                "unsupported",
                f"{engine} sandbox runtime is unavailable ({'; '.join(runtime_errors)}).",
            )
        return (
            "unsupported",
            "gemini sandbox runtime is unavailable (docker/podman not found).",
        )


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


class _GeminiAuthHint:
    def _read_gemini_selected_auth_type(self, *, agent_manager: AgentCliManager) -> str | None:
        settings_path = agent_manager.profile.agent_home / ".gemini" / "settings.json"
        if not settings_path.exists():
            return None
        try:
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        security = payload.get("security")
        if not isinstance(security, dict):
            return None
        auth = security.get("auth")
        if not isinstance(auth, dict):
            return None
        selected = auth.get("selectedType")
        if isinstance(selected, str) and selected.strip():
            return selected.strip()
        return None

    def apply(
        self,
        *,
        agent_manager: AgentCliManager,
        sandbox_enabled: bool,
        sandbox_status: str,
        sandbox_message: str,
    ) -> tuple[bool, str, str]:
        selected = self._read_gemini_selected_auth_type(agent_manager=agent_manager)
        if not selected:
            return (sandbox_enabled, sandbox_status, sandbox_message)
        if "api-key" not in selected.lower():
            return (sandbox_enabled, sandbox_status, sandbox_message)
        return (
            False,
            "unsupported",
            "gemini inline TUI disables --sandbox when security.auth.selectedType is gemini-api-key.",
        )


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
        if strategy == "gemini_container":
            return _GeminiSandboxProbe()
        if strategy == "static_supported":
            return _StaticSupportedSandboxProbe(message=message)
        return _StaticUnsupportedSandboxProbe(message=message)

    def _resolve_auth_hint_strategy(self, profile: AdapterProfile) -> AuthHintStrategy:
        if profile.ui_shell.auth_hint_strategy == "gemini_api_key_disables_sandbox":
            return _GeminiAuthHint()
        return _NoopAuthHint()

    def _resolve_session_security_strategy(self, profile: AdapterProfile) -> SessionSecurityStrategy:
        if profile.resolve_ui_shell_target_relpath() is None:
            return _NoopSecurity()
        return ProfiledJsonSessionSecurity(profile)

    def _build_capability(self, engine: str) -> EngineShellCapability:
        profile = self._load_profile(engine)
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
        )

    def _build_capabilities(self) -> dict[str, EngineShellCapability]:
        return {engine: self._build_capability(engine) for engine in supported_engines()}

    def get(self, engine: str) -> EngineShellCapability | None:
        return self._capabilities.get(engine.strip().lower())

    def list_capabilities(self) -> tuple[EngineShellCapability, ...]:
        return tuple(self._capabilities.values())
