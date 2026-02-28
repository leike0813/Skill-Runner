from __future__ import annotations

import os
from pathlib import Path

from server.services.orchestration.engine_auth_flow_manager import EngineAuthFlowManager
from server.services.orchestration.engine_interaction_gate import EngineInteractionGate


class _Profile:
    def __init__(self, root: Path) -> None:
        self.data_dir = root / "data"
        self.agent_home = root / "agent_home"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.agent_home.mkdir(parents=True, exist_ok=True)

    def build_subprocess_env(self, base_env=None):
        env = dict(base_env or os.environ)
        env["HOME"] = str(self.agent_home)
        env["XDG_CONFIG_HOME"] = str(self.agent_home / ".config")
        env["XDG_DATA_HOME"] = str(self.agent_home / ".local" / "share")
        env["XDG_STATE_HOME"] = str(self.agent_home / ".local" / "state")
        env["XDG_CACHE_HOME"] = str(self.agent_home / ".cache")
        return env


class _AgentManager:
    def __init__(self, profile: _Profile, command_path: Path) -> None:
        self.profile = profile
        self._command_path = command_path

    def resolve_engine_command(self, _engine: str):
        return self._command_path

    def collect_auth_status(self):
        return {
            "codex": {"auth_ready": False},
            "gemini": {"auth_ready": False},
            "iflow": {"auth_ready": False},
            "opencode": {"auth_ready": False},
        }


class _NoopTrust:
    def bootstrap_parent_trust(self, _runs_parent: Path) -> None:
        return None

    def register_run_folder(self, _engine: str, _run_dir: Path) -> None:
        return None

    def remove_run_folder(self, _engine: str, _run_dir: Path) -> None:
        return None


def _write_dummy_command(path: Path) -> Path:
    path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_driver_matrix_registration_and_method_resolution(tmp_path: Path) -> None:
    profile = _Profile(tmp_path)
    command = _write_dummy_command(tmp_path / "dummy-cli")
    manager = EngineAuthFlowManager(
        agent_manager=_AgentManager(profile, command),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_NoopTrust(),
    )

    assert manager._driver_registry.supports(  # noqa: SLF001
        transport="oauth_proxy",
        engine="codex",
        auth_method="callback",
    )
    assert manager._driver_registry.supports(  # noqa: SLF001
        transport="oauth_proxy",
        engine="opencode",
        auth_method="auth_code_or_url",
        provider_id="openai",
    )
    assert manager._driver_registry.supports(  # noqa: SLF001
        transport="cli_delegate",
        engine="iflow",
        auth_method="auth_code_or_url",
    )
    assert manager.resolve_transport_start_method(
        transport="cli_delegate",
        engine="iflow",
        auth_method="auth_code_or_url",
    ) == "iflow-cli-oauth"
    assert manager.resolve_transport_start_method(
        transport="oauth_proxy",
        engine="codex",
        auth_method="callback",
    ) == "auth"
