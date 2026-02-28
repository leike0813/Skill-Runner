import os
from pathlib import Path

from server.services.engine_auth_flow_manager import EngineAuthFlowManager
from server.services.engine_interaction_gate import EngineInteractionGate


class _FakeProfile:
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


class _FakeCliManager:
    def __init__(self, profile: _FakeProfile, command_path: Path) -> None:
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


class _TrustNoop:
    def bootstrap_parent_trust(self, _runs_parent: Path) -> None:
        return

    def register_run_folder(self, _engine: str, _run_dir: Path) -> None:
        return

    def remove_run_folder(self, _engine: str, _run_dir: Path) -> None:
        return


def _write_script(path: Path, body: str) -> Path:
    script = "#!/usr/bin/env bash\nset -e\n" + body + "\n"
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_session_starter_codex_oauth_callback(tmp_path: Path, monkeypatch):
    command_path = _write_script(tmp_path / "fake-codex", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustNoop(),
    )
    monkeypatch.setattr(
        manager,
        "start_callback_listener",
        lambda *, channel, callback_handler: (True, "http://127.0.0.1:1455/auth/callback"),
    )
    monkeypatch.setattr(
        manager,
        "stop_callback_listener",
        lambda *, channel: None,
    )

    plan = manager._session_start_planner.plan_start(  # noqa: SLF001
        engine="codex",
        method="auth",
        auth_method="callback",
        transport="oauth_proxy",
    )
    with manager._lock:  # noqa: SLF001
        manager.interaction_gate.acquire("auth_flow", session_id="starter-codex", engine="codex")
        payload = manager._session_starter.start_from_plan_locked(  # noqa: SLF001
            plan=plan,
            session_id="starter-codex",
        )

    assert payload["session_id"] == "starter-codex"
    assert payload["engine"] == "codex"
    assert payload["transport"] == "oauth_proxy"
    assert payload["status"] == "waiting_user"
    assert payload["execution_mode"] == "protocol_proxy"
    assert str(payload["auth_url"]).startswith("https://auth.openai.com/oauth/authorize?")


def test_session_starter_opencode_api_key_waiting_user(tmp_path: Path):
    command_path = _write_script(tmp_path / "fake-opencode", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustNoop(),
    )

    plan = manager._session_start_planner.plan_start(  # noqa: SLF001
        engine="opencode",
        method="auth",
        auth_method="api_key",
        provider_id="deepseek",
        transport="oauth_proxy",
    )
    with manager._lock:  # noqa: SLF001
        manager.interaction_gate.acquire("auth_flow", session_id="starter-opencode", engine="opencode")
        payload = manager._session_starter.start_from_plan_locked(  # noqa: SLF001
            plan=plan,
            session_id="starter-opencode",
        )

    assert payload["session_id"] == "starter-opencode"
    assert payload["engine"] == "opencode"
    assert payload["provider_id"] == "deepseek"
    assert payload["status"] == "waiting_user"
    assert payload["input_kind"] == "api_key"
    assert payload["execution_mode"] == "protocol_proxy"
