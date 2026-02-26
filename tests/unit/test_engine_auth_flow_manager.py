import os
import time
from pathlib import Path

from server.services.engine_auth_flow_manager import EngineAuthFlowManager
from server.services.engine_interaction_gate import EngineInteractionBusyError, EngineInteractionGate


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
        auth_file = self.profile.agent_home / ".codex" / "auth.json"
        opencode_auth = self.profile.agent_home / ".local" / "share" / "opencode" / "auth.json"
        return {
            "codex": {"auth_ready": auth_file.exists()},
            "gemini": {"auth_ready": False},
            "iflow": {"auth_ready": False},
            "opencode": {"auth_ready": opencode_auth.exists()},
        }


class _TrustSpy:
    def __init__(self) -> None:
        self.bootstrap_calls: list[Path] = []
        self.register_calls: list[tuple[str, Path]] = []
        self.remove_calls: list[tuple[str, Path]] = []

    def bootstrap_parent_trust(self, runs_parent: Path) -> None:
        self.bootstrap_calls.append(runs_parent)

    def register_run_folder(self, engine: str, run_dir: Path) -> None:
        self.register_calls.append((engine, run_dir))

    def remove_run_folder(self, engine: str, run_dir: Path) -> None:
        self.remove_calls.append((engine, run_dir))


def _write_script(path: Path, body: str) -> Path:
    script = "#!/usr/bin/env bash\nset -e\n" + body + "\n"
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)
    return path


def _wait_until_terminal(manager: EngineAuthFlowManager, session_id: str, timeout_sec: float = 3.0):
    deadline = time.time() + timeout_sec
    payload = manager.get_session(session_id)
    while time.time() < deadline:
        payload = manager.get_session(session_id)
        if payload["terminal"]:
            return payload
        time.sleep(0.05)
    return payload


def test_engine_auth_flow_manager_success_parses_challenge(tmp_path: Path):
    command_path = _write_script(
        tmp_path / "fake-codex",
        """
printf 'Open this URL in your browser: https://auth.example.dev/device\033[0m\n'
printf 'Enter code: \033[32mTEST-1234\033[0m\n'
sleep 0.15
mkdir -p "$HOME/.codex"
echo '{"token":"ok"}' > "$HOME/.codex/auth.json"
exit 0
""".strip(),
    )
    profile = _FakeProfile(tmp_path)
    trust_spy = _TrustSpy()
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=trust_spy,
    )

    started = manager.start_session("codex", "device-auth")
    assert started["engine"] == "codex"
    assert started["status"] in {"starting", "waiting_user"}

    final = _wait_until_terminal(manager, started["session_id"])
    assert final["status"] == "succeeded"
    assert final["auth_ready"] is True
    assert final["auth_url"] == "https://auth.example.dev/device"
    assert final["user_code"] == "TEST-1234"
    assert trust_spy.bootstrap_calls == [profile.data_dir / "engine_auth_sessions"]
    assert trust_spy.register_calls
    assert trust_spy.remove_calls


def test_engine_auth_flow_manager_cancel(tmp_path: Path):
    command_path = _write_script(
        tmp_path / "fake-codex",
        """
echo "Open this URL in your browser: https://auth.example.dev/device"
echo "Enter code: LONG-0001"
sleep 5
exit 0
""".strip(),
    )
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    started = manager.start_session("codex", "device-auth")
    canceled = manager.cancel_session(started["session_id"])
    assert canceled["status"] == "canceled"
    assert canceled["terminal"] is True


def test_engine_auth_flow_manager_ttl_expired(tmp_path: Path, monkeypatch):
    command_path = _write_script(
        tmp_path / "fake-codex",
        """
echo "Open this URL in your browser: https://auth.example.dev/device"
echo "Enter code: EXP-1111"
sleep 3
exit 0
""".strip(),
    )
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )
    monkeypatch.setattr(manager, "_ttl_seconds", lambda: 1)

    started = manager.start_session("codex", "device-auth")
    time.sleep(1.2)
    payload = manager.get_session(started["session_id"])
    assert payload["status"] == "expired"
    assert payload["terminal"] is True


def test_engine_auth_flow_manager_rejects_unsupported_engine(tmp_path: Path):
    command_path = _write_script(tmp_path / "fake-codex", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    try:
        manager.start_session("gemini", "device-auth")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "screen-reader-google-oauth" in str(exc)


def test_engine_auth_flow_manager_respects_global_gate_conflict(tmp_path: Path):
    command_path = _write_script(tmp_path / "fake-codex", "sleep 1")
    profile = _FakeProfile(tmp_path)
    gate = EngineInteractionGate()
    gate.acquire("ui_tui", session_id="tui-1", engine="codex")
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=gate,
        trust_manager=_TrustSpy(),
    )

    try:
        manager.start_session("codex", "device-auth")
        raise AssertionError("expected EngineInteractionBusyError")
    except EngineInteractionBusyError:
        pass


def _wait_until_status(
    manager: EngineAuthFlowManager,
    session_id: str,
    expected: set[str],
    timeout_sec: float = 3.0,
):
    deadline = time.time() + timeout_sec
    payload = manager.get_session(session_id)
    while time.time() < deadline:
        payload = manager.get_session(session_id)
        if str(payload.get("status")) in expected:
            return payload
        time.sleep(0.05)
    return payload


def test_engine_auth_flow_manager_gemini_submit_success(tmp_path: Path):
    command_path = _write_script(
        tmp_path / "fake-gemini",
        """
printf 'How would you like to authenticate for this project?\\n'
printf '(checked) 1. Login with Google\\n'
printf '(Use Enter to select)\\n'
IFS= read -r _menu
printf 'Please visit the following URL to authorize the application:\\n\\n'
printf 'https://accounts.google.com/o/oauth2/v2/auth?redirect_uri=https%3A%2F%2Fcodeassist.google.com%2Fauthcode&access_type=off\\n'
printf 'line&scope=openid\\n\\n'
printf 'Enter the authorization code:\\n'
IFS= read -r _code
printf 'Type your message or @path/to/file\\n'
sleep 0.2
""".strip(),
    )
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    started = manager.start_session("gemini", "screen-reader-google-oauth")
    waiting = _wait_until_status(manager, started["session_id"], {"waiting_user"})
    assert waiting["engine"] == "gemini"
    assert waiting["status"] == "waiting_user"
    assert str(waiting["auth_url"]).startswith("https://accounts.google.com/o/oauth2")
    assert "offline" in str(waiting["auth_url"])

    submitted = manager.input_session(started["session_id"], "code", "ABCD-EFGH")
    assert submitted["status"] in {"code_submitted_waiting_result", "succeeded"}

    final = _wait_until_status(manager, started["session_id"], {"succeeded"})
    assert final["status"] == "succeeded"
    assert final["auth_ready"] is True


def test_engine_auth_flow_manager_gemini_already_authenticated_triggers_reauth(tmp_path: Path):
    command_path = _write_script(
        tmp_path / "fake-gemini-authenticated",
        """
printf 'Type your message or @path/to/file\\n'
IFS= read -r first
if [ "$first" = "/auth" ]; then
  printf 'Please visit the following URL to authorize the application:\\n\\n'
  printf 'https://accounts.google.com/o/oauth2/v2/auth?client_id=abc123\\n\\n'
  printf 'Enter the authorization code:\\n'
  IFS= read -r _code
  printf 'Type your message or @path/to/file\\n'
fi
sleep 0.2
""".strip(),
    )
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    started = manager.start_session("gemini", "screen-reader-google-oauth")
    waiting = _wait_until_status(manager, started["session_id"], {"waiting_user"})
    assert waiting["status"] == "waiting_user"
    assert waiting["auth_url"] == "https://accounts.google.com/o/oauth2/v2/auth?client_id=abc123"


def test_engine_auth_flow_manager_iflow_submit_success(tmp_path: Path):
    command_path = _write_script(
        tmp_path / "fake-iflow",
        """
printf 'iFlow OAuth 登录\\n'
printf '1. 请复制以下链接并在浏览器中打开：\\n'
printf 'https://iflow.cn/oauth?state=abc123\\n'
printf '2. 登录您的心流账号并授权\\n'
printf '授权码：\\n'
printf '粘贴授权码...\\n'
IFS= read -r _code
printf '模型选择\\n'
printf '按回车使用默认选择：GLM 4.7\\n'
IFS= read -r _model
printf '输入消息或@文件路径\\n'
sleep 0.2
""".strip(),
    )
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    started = manager.start_session("iflow", "iflow-cli-oauth")
    waiting = _wait_until_status(manager, started["session_id"], {"waiting_user"})
    assert waiting["engine"] == "iflow"
    assert waiting["status"] == "waiting_user"
    assert str(waiting["auth_url"]).startswith("https://iflow.cn/oauth?")

    submitted = manager.input_session(started["session_id"], "code", "CODE-1234")
    assert submitted["status"] in {"code_submitted_waiting_result", "succeeded"}

    final = _wait_until_status(manager, started["session_id"], {"succeeded"})
    assert final["status"] == "succeeded"
    assert final["auth_ready"] is True


def test_engine_auth_flow_manager_iflow_rejects_wrong_method(tmp_path: Path):
    command_path = _write_script(tmp_path / "fake-iflow", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    try:
        manager.start_session("iflow", "device-auth")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "iflow-cli-oauth" in str(exc)


def test_engine_auth_flow_manager_opencode_api_key_success(tmp_path: Path):
    command_path = _write_script(tmp_path / "fake-opencode", "sleep 1")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    started = manager.start_session("opencode", "opencode-provider-auth", "deepseek")
    assert started["engine"] == "opencode"
    assert started["status"] == "waiting_user"
    assert started["input_kind"] == "api_key"
    assert started["provider_id"] == "deepseek"

    submitted = manager.input_session(started["session_id"], "api_key", "sk-test-123")
    assert submitted["status"] == "succeeded"
    assert submitted["auth_ready"] is True

    auth_path = profile.agent_home / ".local" / "share" / "opencode" / "auth.json"
    assert auth_path.exists()
    payload = auth_path.read_text(encoding="utf-8")
    assert "deepseek" in payload
    assert "sk-test-123" in payload


def test_engine_auth_flow_manager_opencode_google_cleanup_failure(tmp_path: Path, monkeypatch):
    command_path = _write_script(tmp_path / "fake-opencode", "sleep 1")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    class _BrokenStore:
        def backup_antigravity_accounts(self, _backup_path):
            return {"source_exists": False, "backup_created": False, "backup_path": None}

        def clear_antigravity_accounts(self):
            raise RuntimeError("boom")

        def restore_antigravity_accounts(self, *, source_exists, backup_path=None):  # noqa: ARG002
            return None

    monkeypatch.setattr(manager, "_build_opencode_auth_store", lambda: _BrokenStore())
    payload = manager.start_session("opencode", "opencode-provider-auth", "google")
    assert payload["status"] == "failed"
    assert payload["terminal"] is True
    assert payload["audit"]["google_antigravity_cleanup"]["success"] is False


def test_engine_auth_flow_manager_opencode_openai_enters_waiting_user(tmp_path: Path):
    command_path = _write_script(
        tmp_path / "fake-opencode-openai",
        """
printf 'Login method\\n'
printf '●  Go to: https://auth.openai.com/oauth/authorize?state=abc123&originator=opencode\\n'
printf '●  Complete authorization in your browser. This window will close automatically.\\n'
printf '◒  Waiting for authorization\\n'
sleep 2
""".strip(),
    )
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    started = manager.start_session("opencode", "opencode-provider-auth", "openai")
    waiting = _wait_until_status(manager, started["session_id"], {"waiting_user"})
    assert waiting["status"] == "waiting_user"
    assert waiting["provider_id"] == "openai"
    assert str(waiting["auth_url"]).startswith("https://auth.openai.com/oauth/authorize?")


def test_engine_auth_flow_manager_opencode_google_cancel_restores_accounts(tmp_path: Path):
    command_path = _write_script(tmp_path / "fake-opencode", "sleep 10")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    accounts_path = profile.agent_home / ".config" / "opencode" / "antigravity-accounts.json"
    accounts_path.parent.mkdir(parents=True, exist_ok=True)
    accounts_path.write_text(
        '{"accounts":[{"id":"legacy"}],"active":"legacy","activeIndex":0}\n',
        encoding="utf-8",
    )

    started = manager.start_session("opencode", "opencode-provider-auth", "google")
    assert started["engine"] == "opencode"
    assert started["provider_id"] == "google"
    cleared = accounts_path.read_text(encoding="utf-8")
    assert '"accounts": []' in cleared

    canceled = manager.cancel_session(started["session_id"])
    assert canceled["status"] == "canceled"
    rollback = canceled["audit"]["google_antigravity_cleanup"]
    assert rollback["rollback_attempted"] is True
    assert rollback["rollback_success"] is True

    restored = accounts_path.read_text(encoding="utf-8")
    assert '"legacy"' in restored
