from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Protocol

from server.services.engine_management.agent_cli_manager import AgentCliManager
from server.services.engine_management.engine_command_profile import (
    EngineCommandProfile,
)
from server.services.engine_management.engine_catalog import supported_engines


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


class SandboxProbeStrategy(Protocol):
    def probe(self, *, agent_manager: AgentCliManager, engine: str) -> tuple[str, str]:
        ...


class SessionSecurityStrategy(Protocol):
    def prepare(self, *, session_dir: Path, env: Dict[str, str], sandbox_enabled: bool) -> None:
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
    def prepare(self, *, session_dir: Path, env: Dict[str, str], sandbox_enabled: bool) -> None:
        _ = (session_dir, env, sandbox_enabled)


class _GeminiSecurity:
    def prepare(self, *, session_dir: Path, env: Dict[str, str], sandbox_enabled: bool) -> None:
        _ = env
        _write_json(
            session_dir / ".gemini" / "settings.json",
            {
                "general": {
                    "enableAutoUpdate": False,
                },
                "tools": {
                    "sandbox": sandbox_enabled,
                    "autoAccept": False,
                    "exclude": ["run_shell_command", "ShellTool"],
                },
                "security": {
                    "disableYoloMode": True,
                },
            },
        )


class _IflowSecurity:
    def prepare(self, *, session_dir: Path, env: Dict[str, str], sandbox_enabled: bool) -> None:
        _ = (env, sandbox_enabled)
        _write_json(
            session_dir / ".iflow" / "settings.json",
            {
                "sandbox": False,
                "autoAccept": False,
                "approvalMode": "default",
                "excludeTools": ["ShellTool"],
            },
        )


class _OpencodeSecurity:
    def prepare(self, *, session_dir: Path, env: Dict[str, str], sandbox_enabled: bool) -> None:
        _ = (env, sandbox_enabled)
        _write_json(
            session_dir / "opencode.json",
            {
                "permission": "deny",
            },
        )


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
    def __init__(self, command_profile: EngineCommandProfile | None = None) -> None:
        self._command_profile = command_profile or EngineCommandProfile()
        self._capabilities = self._build_capabilities()

    def _default_launch_args(self, engine: str) -> tuple[str, ...]:
        defaults: dict[str, tuple[str, ...]] = {
            "codex": (
                "--sandbox",
                "workspace-write",
                "--ask-for-approval",
                "never",
                "-c",
                "features.shell_tool=false",
                "-c",
                "features.unified_exec=false",
            ),
            "gemini": (
                "--sandbox",
                "--approval-mode",
                "default",
            ),
            "iflow": (),
            "opencode": (),
        }
        return defaults.get(engine, ())

    def _resolve_launch_args(self, engine: str) -> tuple[str, ...]:
        args = self._command_profile.resolve_args(engine=engine, action="ui_shell")
        if args:
            return tuple(args)
        return self._default_launch_args(engine)

    def _build_capabilities(self) -> dict[str, EngineShellCapability]:
        capabilities: dict[str, EngineShellCapability] = {
            "codex": EngineShellCapability(
                command_id="codex-tui",
                label="Codex TUI",
                engine="codex",
                launch_args=self._resolve_launch_args("codex"),
                trust_bootstrap_parent=True,
                sandbox_arg="--sandbox",
                retry_without_sandbox_on_early_exit=False,
                sandbox_probe_strategy=_CodexSandboxProbe(),
                session_security_strategy=_NoopSecurity(),
                auth_hint_strategy=_NoopAuthHint(),
            ),
            "gemini": EngineShellCapability(
                command_id="gemini-tui",
                label="Gemini TUI",
                engine="gemini",
                launch_args=self._resolve_launch_args("gemini"),
                trust_bootstrap_parent=True,
                sandbox_arg="--sandbox",
                retry_without_sandbox_on_early_exit=True,
                sandbox_probe_strategy=_GeminiSandboxProbe(),
                session_security_strategy=_GeminiSecurity(),
                auth_hint_strategy=_GeminiAuthHint(),
            ),
            "iflow": EngineShellCapability(
                command_id="iflow-tui",
                label="iFlow TUI",
                engine="iflow",
                launch_args=self._resolve_launch_args("iflow"),
                trust_bootstrap_parent=False,
                sandbox_arg=None,
                retry_without_sandbox_on_early_exit=False,
                sandbox_probe_strategy=_StaticUnsupportedSandboxProbe(
                    message=(
                        "iFlow inline TUI runs without sandbox. iFlow sandbox requires Docker-image "
                        "execution, which is intentionally outside this inline TUI design."
                    )
                ),
                session_security_strategy=_IflowSecurity(),
                auth_hint_strategy=_NoopAuthHint(),
            ),
            "opencode": EngineShellCapability(
                command_id="opencode-tui",
                label="OpenCode TUI",
                engine="opencode",
                launch_args=self._resolve_launch_args("opencode"),
                trust_bootstrap_parent=False,
                sandbox_arg=None,
                retry_without_sandbox_on_early_exit=False,
                sandbox_probe_strategy=_StaticUnsupportedSandboxProbe(
                    message="OpenCode inline TUI runs without sandbox."
                ),
                session_security_strategy=_OpencodeSecurity(),
                auth_hint_strategy=_NoopAuthHint(),
            ),
        }
        for engine in supported_engines():
            if engine not in capabilities:
                capabilities[engine] = EngineShellCapability(
                    command_id=f"{engine}-tui",
                    label=f"{engine} TUI",
                    engine=engine,
                    launch_args=self._resolve_launch_args(engine),
                    trust_bootstrap_parent=False,
                    sandbox_arg=None,
                    retry_without_sandbox_on_early_exit=False,
                    sandbox_probe_strategy=_StaticUnsupportedSandboxProbe(
                        message="Sandbox capability is unknown for this engine."
                    ),
                    session_security_strategy=_NoopSecurity(),
                    auth_hint_strategy=_NoopAuthHint(),
                )
        return capabilities

    def get(self, engine: str) -> EngineShellCapability | None:
        return self._capabilities.get(engine.strip().lower())

    def list_capabilities(self) -> tuple[EngineShellCapability, ...]:
        return tuple(self._capabilities.values())

