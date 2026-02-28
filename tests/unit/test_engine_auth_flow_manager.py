import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from server.config import config
from server.engines.codex.auth import CodexOAuthProxySession
from server.engines.gemini.auth import GeminiOAuthProxySession
from server.engines.iflow.auth import IFlowOAuthProxySession
from server.engines.opencode.auth import (
    OpencodeAuthCliSession,
    OpencodeGoogleAntigravityOAuthProxySession,
)
from server.runtime.auth.session_lifecycle import AuthStartPlan
from server.services.orchestration.engine_auth_flow_manager import EngineAuthFlowManager
from server.services.orchestration.engine_interaction_gate import EngineInteractionBusyError, EngineInteractionGate
from server.engines.common.openai_auth import OpenAIDeviceProxySession, OpenAIOAuthError


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


def _set_google_oauth_proxy_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "SKILL_RUNNER_GEMINI_OAUTH_CLIENT_ID",
        "test-gemini-client-id.apps.googleusercontent.com",
    )
    monkeypatch.setenv(
        "SKILL_RUNNER_GEMINI_OAUTH_CLIENT_SECRET",
        "test-gemini-client-secret",
    )
    monkeypatch.setenv(
        "SKILL_RUNNER_OPENCODE_GOOGLE_OAUTH_CLIENT_ID",
        "test-opencode-google-client-id.apps.googleusercontent.com",
    )
    monkeypatch.setenv(
        "SKILL_RUNNER_OPENCODE_GOOGLE_OAUTH_CLIENT_SECRET",
        "test-opencode-google-client-secret",
    )


def test_engine_auth_flow_manager_codex_oauth_proxy_uses_protocol_flow(tmp_path: Path, monkeypatch):
    command_path = _write_script(tmp_path / "fake-codex", "exit 0")
    profile = _FakeProfile(tmp_path)
    trust_spy = _TrustSpy()
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=trust_spy,
    )
    listener_calls = {"start": 0, "stop": 0}

    submit_calls: list[str] = []

    def _fake_submit(runtime, value):  # noqa: ANN001
        submit_calls.append(value)
        auth_path = profile.agent_home / ".codex" / "auth.json"
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        auth_path.write_text("{\"tokens\":{}}\n", encoding="utf-8")

    monkeypatch.setattr(manager._codex_oauth_proxy_flow, "submit_input", _fake_submit)
    monkeypatch.setattr(
        "server.engines.common.callbacks.openai_local_callback_server.set_callback_handler",
        lambda _handler: None,
    )
    def _fake_listener_start() -> bool:
        listener_calls["start"] = listener_calls["start"] + 1
        return True

    def _fake_listener_stop() -> None:
        listener_calls["stop"] = listener_calls["stop"] + 1

    monkeypatch.setattr(
        "server.engines.common.callbacks.openai_local_callback_server.start",
        _fake_listener_start,
    )
    monkeypatch.setattr(
        "server.engines.common.callbacks.openai_local_callback_server.stop",
        _fake_listener_stop,
    )

    started = manager.start_session("codex", "auth", auth_method="callback")
    assert started["engine"] == "codex"
    assert started["transport"] == "oauth_proxy"
    assert started["method"] == "auth"
    assert started["status"] == "waiting_user"
    assert str(started["auth_url"]).startswith("https://auth.openai.com/oauth/authorize?")
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A1455%2Fauth%2Fcallback" in str(started["auth_url"])

    final = manager.input_session(started["session_id"], "text", "http://localhost/callback?code=test-code")
    assert final["status"] == "succeeded"
    assert final["auth_ready"] is True
    assert final["manual_fallback_used"] is True
    assert submit_calls == ["http://localhost/callback?code=test-code"]
    assert final["auth_url"].startswith("https://auth.openai.com/oauth/authorize?")
    assert trust_spy.bootstrap_calls == [profile.data_dir / "engine_auth_sessions"]
    assert trust_spy.register_calls
    assert trust_spy.remove_calls
    assert listener_calls["start"] == 1
    assert listener_calls["stop"] == 1


def test_engine_auth_flow_manager_extract_auth_url_prefers_non_localhost(tmp_path: Path):
    command_path = _write_script(tmp_path / "fake-codex", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )
    text = (
        "Starting local login server on http://localhost:1455.\n"
        "If your browser did not open, navigate to this URL to authenticate:\n"
        "https://auth.openai.com/oauth/authorize?client_id=abc&state=xyz\n"
    )
    extracted = manager._extract_auth_url(text)  # noqa: SLF001
    assert extracted == "https://auth.openai.com/oauth/authorize?client_id=abc&state=xyz"


def test_engine_auth_flow_manager_start_delegates_to_session_starter(tmp_path: Path, monkeypatch):
    command_path = _write_script(tmp_path / "fake-codex", "exit 0")
    profile = _FakeProfile(tmp_path)
    gate = EngineInteractionGate()
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=gate,
        trust_manager=_TrustSpy(),
    )

    stub_plan = AuthStartPlan(
        engine="codex",
        method="auth",
        auth_method="callback",
        transport="oauth_proxy",
        provider_id=None,
        provider=None,
        registry_provider_id=None,
        command=None,
        requires_command=False,
    )
    monkeypatch.setattr(
        manager._session_start_planner,  # noqa: SLF001
        "plan_start",
        lambda **_kwargs: stub_plan,
    )

    called: dict[str, str | None] = {}

    def _fake_start_from_plan_locked(*, plan, session_id, callback_base_url=None):  # noqa: ANN001
        called["plan_engine"] = plan.engine
        called["session_id"] = session_id
        called["callback_base_url"] = callback_base_url
        return {
            "session_id": session_id,
            "engine": plan.engine,
            "transport": plan.transport,
            "auth_method": plan.auth_method,
            "terminal": False,
        }

    monkeypatch.setattr(
        manager._session_starter,  # noqa: SLF001
        "start_from_plan_locked",
        _fake_start_from_plan_locked,
    )

    started = manager.start_session("codex", "auth", transport="oauth_proxy", auth_method="callback")
    assert started["engine"] == "codex"
    assert called["plan_engine"] == "codex"
    assert isinstance(called["session_id"], str)

    gate.release("auth_flow", str(called["session_id"]))


def test_engine_auth_flow_manager_codex_oauth_proxy_zero_cli(tmp_path: Path, monkeypatch):
    command_path = _write_script(tmp_path / "fake-codex", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    def _raise(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("subprocess should not be called in oauth_proxy mode")

    monkeypatch.setattr("server.services.orchestration.engine_auth_flow_manager.subprocess.Popen", _raise)
    started = manager.start_session("codex", "auth", transport="oauth_proxy", auth_method="callback")
    assert started["status"] == "waiting_user"
    assert started["execution_mode"] == "protocol_proxy"


def test_engine_auth_flow_manager_codex_cli_delegate_uses_browser_login(tmp_path: Path, monkeypatch):
    command_path = _write_script(tmp_path / "fake-codex", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )
    captured: list[list[str]] = []

    class _FakeProc:
        pid = 12345
        stdin = None

        def poll(self):  # noqa: ANN201
            return None

    def _fake_popen(cmd, **kwargs):  # noqa: ANN001, ANN003
        captured.append(list(cmd))
        return _FakeProc()

    monkeypatch.setattr(
        "server.engines.common.callbacks.openai_local_callback_server.start",
        lambda: (_ for _ in ()).throw(AssertionError("listener should not start for cli_delegate")),
    )
    monkeypatch.setattr("server.services.orchestration.engine_auth_flow_manager.subprocess.Popen", _fake_popen)
    started = manager.start_session("codex", "auth", transport="cli_delegate", auth_method="callback")
    assert started["transport"] == "cli_delegate"
    assert started["method"] == "auth"
    assert started["status"] == "waiting_user"
    assert started["input_kind"] == "text"
    assert captured == [[str(command_path), "login"]]


def test_engine_auth_flow_manager_opencode_openai_cli_delegate_callback_shows_input(
    tmp_path: Path,
    monkeypatch,
):
    command_path = _write_script(tmp_path / "fake-opencode", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    class _FakeProc:
        pid = 12346

        def poll(self):  # noqa: ANN201
            return None

    def _fake_start_session(**kwargs):  # noqa: ANN003
        now = datetime.now(timezone.utc)
        return OpencodeAuthCliSession(
            session_id=str(kwargs.get("session_id", "s")),
            process=_FakeProc(),
            master_fd=0,
            output_path=Path(kwargs.get("output_path")),
            created_at=now,
            updated_at=now,
            expires_at=kwargs.get("expires_at"),
            provider_id="openai",
            provider_label="OpenAI",
            openai_auth_method="callback",
            status="waiting_user",
        )

    monkeypatch.setattr(manager._opencode_flow, "start_session", _fake_start_session)
    monkeypatch.setattr(manager._opencode_flow, "refresh", lambda _runtime: None)

    started = manager.start_session(
        "opencode",
        "auth",
        transport="cli_delegate",
        provider_id="openai",
        auth_method="callback",
    )
    assert started["transport"] == "cli_delegate"
    assert started["provider_id"] == "openai"
    assert started["status"] == "waiting_user"
    assert started["input_kind"] == "text"


def test_engine_auth_flow_manager_cancel_releases_lock_on_terminate_error(tmp_path: Path, monkeypatch):
    command_path = _write_script(tmp_path / "fake-codex", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )
    captured: list[list[str]] = []

    class _FakeProc:
        pid = 12347
        stdin = None

        def poll(self):  # noqa: ANN201
            return None

    def _fake_popen(cmd, **kwargs):  # noqa: ANN001, ANN003
        captured.append(list(cmd))
        return _FakeProc()

    monkeypatch.setattr("server.services.orchestration.engine_auth_flow_manager.subprocess.Popen", _fake_popen)
    started = manager.start_session("codex", "auth", transport="cli_delegate", auth_method="callback")

    monkeypatch.setattr(manager, "_terminate_process", lambda _session: (_ for _ in ()).throw(RuntimeError("boom")))
    canceled = manager.cancel_session(started["session_id"])
    assert canceled["status"] == "canceled"
    assert canceled["terminal"] is True
    assert "terminate error" in str(canceled["error"])

    followup = manager.start_session("codex", "auth", transport="cli_delegate", auth_method="callback")
    assert followup["status"] == "waiting_user"
    assert len(captured) == 2


def test_engine_auth_flow_manager_codex_oauth_proxy_respects_configured_callback_base(
    tmp_path: Path,
):
    command_path = _write_script(tmp_path / "fake-codex", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )
    previous = str(config.SYSTEM.ENGINE_AUTH_OAUTH_CALLBACK_BASE_URL)
    try:
        config.defrost()
        config.SYSTEM.ENGINE_AUTH_OAUTH_CALLBACK_BASE_URL = "https://oauth.skill-runner.dev"
        config.freeze()
        started = manager.start_session("codex", "auth", transport="oauth_proxy", auth_method="callback")
        assert (
            "redirect_uri=https%3A%2F%2Foauth.skill-runner.dev%2Fauth%2Fcallback"
            in str(started["auth_url"])
        )
    finally:
        config.defrost()
        config.SYSTEM.ENGINE_AUTH_OAUTH_CALLBACK_BASE_URL = previous
        config.freeze()


def test_engine_auth_flow_manager_openai_callback_state_once(tmp_path: Path, monkeypatch):
    command_path = _write_script(tmp_path / "fake-codex", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )
    started = manager.start_session("codex", "auth", transport="oauth_proxy", auth_method="callback")
    runtime = manager._sessions[started["session_id"]].driver_state
    assert isinstance(runtime, CodexOAuthProxySession)
    state = runtime.state

    def _fake_complete(runtime_obj, code):  # noqa: ANN001
        assert code == "callback-code"
        auth_path = profile.agent_home / ".codex" / "auth.json"
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        auth_path.write_text("{\"tokens\":{}}\n", encoding="utf-8")

    monkeypatch.setattr(manager._codex_oauth_proxy_flow, "complete_with_code", _fake_complete)
    payload = manager.complete_callback(channel="openai", state=state, code="callback-code")
    assert payload["status"] == "succeeded"
    assert payload["oauth_callback_received"] is True
    assert payload["manual_fallback_used"] is False

    try:
        manager.complete_callback(channel="openai", state=state, code="callback-code")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "already been consumed" in str(exc)


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

    started = manager.start_session("codex", "auth", auth_method="auth_code_or_url")
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

    started = manager.start_session("codex", "auth", auth_method="auth_code_or_url")
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
        manager.start_session("gemini", "auth", transport="cli_delegate", auth_method="callback")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "auth_code_or_url" in str(exc)


def test_engine_auth_flow_manager_gemini_oauth_proxy_uses_protocol_flow(tmp_path: Path, monkeypatch):
    _set_google_oauth_proxy_env(monkeypatch)
    command_path = _write_script(tmp_path / "fake-gemini", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )
    listener_calls = {"start": 0, "stop": 0}

    def _fake_listener_start() -> str:
        listener_calls["start"] = listener_calls["start"] + 1
        return "http://127.0.0.1:51122/oauth2callback"

    def _fake_listener_stop() -> None:
        listener_calls["stop"] = listener_calls["stop"] + 1

    monkeypatch.setattr(
        manager,
        "start_callback_listener",
        lambda *, channel, callback_handler: (True, _fake_listener_start()),
    )
    monkeypatch.setattr(manager, "stop_callback_listener", lambda *, channel: _fake_listener_stop())

    started = manager.start_session(
        "gemini",
        "auth",
        transport="oauth_proxy",
        auth_method="auth_code_or_url",
    )
    assert started["engine"] == "gemini"
    assert started["transport"] == "oauth_proxy"
    assert started["auth_method"] == "auth_code_or_url"
    assert started["status"] == "waiting_user"
    assert started["execution_mode"] == "protocol_proxy"
    assert "accounts.google.com/o/oauth2/v2/auth" in str(started["auth_url"])
    assert listener_calls["start"] == 0

    runtime = manager._sessions[started["session_id"]].driver_state  # noqa: SLF001
    assert isinstance(runtime, GeminiOAuthProxySession)

    monkeypatch.setattr(
        manager._gemini_oauth_proxy_flow,
        "submit_input",
        lambda *_args, **_kwargs: {"google_account_email": "test@example.com"},
    )
    monkeypatch.setattr(
        manager,
        "_collect_auth_ready",
        lambda engine: engine == "gemini",
    )
    final = manager.input_session(
        started["session_id"],
        "text",
        f"http://127.0.0.1:51122/oauth2callback?code=code-1&state={runtime.state}",
    )
    assert final["status"] == "succeeded"
    assert final["manual_fallback_used"] is True
    assert final["audit"]["callback_mode"] == "manual"
    assert listener_calls["stop"] == 1


def test_engine_auth_flow_manager_gemini_oauth_proxy_callback_state_once(tmp_path: Path, monkeypatch):
    _set_google_oauth_proxy_env(monkeypatch)
    command_path = _write_script(tmp_path / "fake-gemini", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )
    monkeypatch.setattr(
        manager,
        "start_callback_listener",
        lambda *, channel, callback_handler: (True, "http://127.0.0.1:51122/oauth2callback"),
    )
    monkeypatch.setattr(manager, "stop_callback_listener", lambda *, channel: None)
    monkeypatch.setattr(
        manager._gemini_oauth_proxy_flow,
        "complete_with_code",
        lambda **_kwargs: {"google_account_email": "test@example.com"},
    )
    monkeypatch.setattr(
        manager,
        "_collect_auth_ready",
        lambda engine: engine == "gemini",
    )
    started = manager.start_session(
        "gemini",
        "auth",
        transport="oauth_proxy",
        auth_method="callback",
    )
    runtime = manager._sessions[started["session_id"]].driver_state  # noqa: SLF001
    assert isinstance(runtime, GeminiOAuthProxySession)

    payload = manager.complete_callback(channel="gemini", state=runtime.state, code="callback-code")
    assert payload["status"] == "succeeded"
    assert payload["oauth_callback_received"] is True
    assert payload["manual_fallback_used"] is False

    try:
        manager.complete_callback(channel="gemini", state=runtime.state, code="callback-code")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "already been consumed" in str(exc)


def test_engine_auth_flow_manager_iflow_oauth_proxy_manual_success(tmp_path: Path, monkeypatch):
    command_path = _write_script(tmp_path / "fake-iflow", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )
    listener_calls = {"start": 0, "stop": 0}

    def _fake_listener_start() -> str:
        listener_calls["start"] = listener_calls["start"] + 1
        return "http://127.0.0.1:11451/oauth2callback"

    def _fake_listener_stop() -> None:
        listener_calls["stop"] = listener_calls["stop"] + 1

    monkeypatch.setattr(
        manager,
        "start_callback_listener",
        lambda *, channel, callback_handler: (True, _fake_listener_start()),
    )
    monkeypatch.setattr(manager, "stop_callback_listener", lambda *, channel: _fake_listener_stop())
    monkeypatch.setattr(
        manager._iflow_oauth_proxy_flow,
        "submit_input",
        lambda *_args, **_kwargs: {"iflow_api_key_present": True, "iflow_user_name": "iflow-user"},
    )
    monkeypatch.setattr(manager, "_collect_auth_ready", lambda engine: engine == "iflow")

    started = manager.start_session(
        "iflow",
        "auth",
        transport="oauth_proxy",
        auth_method="auth_code_or_url",
    )
    assert started["engine"] == "iflow"
    assert started["transport"] == "oauth_proxy"
    assert started["status"] == "waiting_user"
    assert started["execution_mode"] == "protocol_proxy"
    assert str(started["auth_url"]).startswith("https://iflow.cn/oauth?")
    assert listener_calls["start"] == 0

    runtime = manager._sessions[started["session_id"]].driver_state  # noqa: SLF001
    assert isinstance(runtime, IFlowOAuthProxySession)
    assert runtime.redirect_uri == "https://iflow.cn/oauth/code-display"
    assert "redirect=https%3A%2F%2Fiflow.cn%2Foauth%2Fcode-display" in str(started["auth_url"])

    submitted = manager.input_session(
        started["session_id"],
        "text",
        f"http://127.0.0.1:11451/oauth2callback?code=iflow-code&state={runtime.state}",
    )
    assert submitted["status"] == "succeeded"
    assert submitted["manual_fallback_used"] is True
    assert submitted["audit"]["callback_mode"] == "manual"
    assert listener_calls["stop"] == 1


def test_engine_auth_flow_manager_iflow_oauth_proxy_callback_state_once(tmp_path: Path, monkeypatch):
    command_path = _write_script(tmp_path / "fake-iflow", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    monkeypatch.setattr(
        manager,
        "start_callback_listener",
        lambda *, channel, callback_handler: (True, "http://127.0.0.1:11451/oauth2callback"),
    )
    monkeypatch.setattr(manager, "stop_callback_listener", lambda *, channel: None)
    monkeypatch.setattr(
        manager._iflow_oauth_proxy_flow,
        "complete_with_code",
        lambda **_kwargs: {"iflow_api_key_present": True, "iflow_user_name": "iflow-user"},
    )
    monkeypatch.setattr(manager, "_collect_auth_ready", lambda engine: engine == "iflow")

    started = manager.start_session(
        "iflow",
        "auth",
        transport="oauth_proxy",
        auth_method="callback",
    )
    runtime = manager._sessions[started["session_id"]].driver_state  # noqa: SLF001
    assert isinstance(runtime, IFlowOAuthProxySession)

    payload = manager.complete_callback(channel="iflow", state=runtime.state, code="callback-code")
    assert payload["status"] == "succeeded"
    assert payload["oauth_callback_received"] is True
    assert payload["manual_fallback_used"] is False

    try:
        manager.complete_callback(channel="iflow", state=runtime.state, code="callback-code")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "already been consumed" in str(exc)


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
        manager.start_session("codex", "auth", auth_method="auth_code_or_url")
        raise AssertionError("expected EngineInteractionBusyError")
    except EngineInteractionBusyError:
        pass


def test_engine_auth_flow_manager_device_proxy_settles_active_before_new_start(
    tmp_path: Path,
    monkeypatch,
):
    command_path = _write_script(tmp_path / "fake-codex", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    state = {"authorized": False}
    poll_calls = {"count": 0}
    now = datetime.now(timezone.utc)

    def _fake_device_start(**_kwargs):  # noqa: ANN003
        return OpenAIDeviceProxySession(
            session_id="fake-device-runtime",
            issuer="https://auth.openai.com",
            client_id="client",
            redirect_uri="https://auth.openai.com/deviceauth/callback",
            device_auth_id="device-auth-id",
            user_code="TEST-CODE",
            verification_url="https://auth.openai.com/device",
            interval_seconds=120,
            user_agent="test-agent",
            created_at=now,
            updated_at=now,
            next_poll_at=now + timedelta(minutes=5),
            completed=False,
        )

    def _fake_poll_once(runtime, *, now):  # noqa: ANN001
        runtime.updated_at = now
        poll_calls["count"] = poll_calls["count"] + 1
        # first start refresh -> call 1 (pending)
        # second start pre-check refresh -> call 2 (still pending)
        # forced settle refresh -> call 3 (authorized -> success)
        if not state["authorized"] or poll_calls["count"] < 3:
            return None
        runtime.completed = True
        return object()

    def _fake_complete_with_tokens(_token_set):  # noqa: ANN001
        auth_path = profile.agent_home / ".codex" / "auth.json"
        auth_path.parent.mkdir(parents=True, exist_ok=True)
        auth_path.write_text("{\"tokens\":{}}\n", encoding="utf-8")

    monkeypatch.setattr(manager._openai_device_proxy_flow, "start_session", _fake_device_start)
    monkeypatch.setattr(manager._openai_device_proxy_flow, "poll_once", _fake_poll_once)
    monkeypatch.setattr(manager._codex_oauth_proxy_flow, "complete_with_tokens", _fake_complete_with_tokens)

    first = manager.start_session(
        "codex",
        "auth",
        auth_method="auth_code_or_url",
        transport="oauth_proxy",
    )
    assert first["status"] == "waiting_user"

    state["authorized"] = True
    second = manager.start_session(
        "codex",
        "auth",
        auth_method="auth_code_or_url",
        transport="oauth_proxy",
    )
    assert second["status"] in {"waiting_user", "succeeded"}
    assert second["session_id"] != first["session_id"]
    assert poll_calls["count"] >= 3

    first_latest = manager.get_session(first["session_id"])
    assert first_latest["status"] == "succeeded"


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

    started = manager.start_session(
        "gemini",
        "auth",
        transport="cli_delegate",
        auth_method="auth_code_or_url",
    )
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

    started = manager.start_session(
        "gemini",
        "auth",
        transport="cli_delegate",
        auth_method="auth_code_or_url",
    )
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

    started = manager.start_session(
        "iflow",
        "auth",
        transport="cli_delegate",
        auth_method="auth_code_or_url",
    )
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
        manager.start_session("iflow", "auth", transport="cli_delegate", auth_method="callback")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "auth_code_or_url" in str(exc)


def test_engine_auth_flow_manager_opencode_api_key_success(tmp_path: Path):
    command_path = _write_script(tmp_path / "fake-opencode", "sleep 1")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    started = manager.start_session(
        "opencode",
        "auth",
        provider_id="deepseek",
        transport="oauth_proxy",
        auth_method="api_key",
    )
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


def test_engine_auth_flow_manager_opencode_api_key_rejects_cli_delegate(tmp_path: Path):
    command_path = _write_script(tmp_path / "fake-opencode", "sleep 1")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    with pytest.raises(ValueError, match="require oauth_proxy transport"):
        manager.start_session(
            "opencode",
            "auth",
            provider_id="deepseek",
            transport="cli_delegate",
            auth_method="api_key",
        )


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
    payload = manager.start_session(
        "opencode",
        "auth",
        provider_id="google",
        transport="cli_delegate",
        auth_method="auth_code_or_url",
    )
    assert payload["status"] == "failed"
    assert payload["terminal"] is True
    assert payload["audit"]["google_antigravity_cleanup"]["success"] is False


def test_engine_auth_flow_manager_opencode_openai_enters_waiting_user(tmp_path: Path, monkeypatch):
    command_path = _write_script(tmp_path / "fake-opencode-openai", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    def _raise(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("subprocess should not be called in oauth_proxy mode")

    monkeypatch.setattr("server.services.orchestration.engine_auth_flow_manager.subprocess.Popen", _raise)

    started = manager.start_session(
        "opencode",
        "auth",
        provider_id="openai",
        auth_method="callback",
    )
    waiting = manager.get_session(started["session_id"])
    assert waiting["status"] == "waiting_user"
    assert waiting["provider_id"] == "openai"
    assert waiting["execution_mode"] == "protocol_proxy"
    assert str(waiting["auth_url"]).startswith("https://auth.openai.com/oauth/authorize?")
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A1455%2Fauth%2Fcallback" in str(waiting["auth_url"])


def test_engine_auth_flow_manager_opencode_google_oauth_proxy_manual_fallback_success(
    tmp_path: Path,
    monkeypatch,
):
    _set_google_oauth_proxy_env(monkeypatch)
    command_path = _write_script(tmp_path / "fake-opencode-google", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )
    listener_calls = {"start": 0, "stop": 0}

    monkeypatch.setattr(
        "server.engines.opencode.auth.callbacks.antigravity_local_callback_server.set_callback_handler",
        lambda _handler: None,
    )
    def _fake_antigravity_listener_start() -> bool:
        listener_calls["start"] = listener_calls["start"] + 1
        return True

    def _fake_antigravity_listener_stop() -> None:
        listener_calls["stop"] = listener_calls["stop"] + 1

    monkeypatch.setattr(
        "server.engines.opencode.auth.callbacks.antigravity_local_callback_server.start",
        _fake_antigravity_listener_start,
    )
    monkeypatch.setattr(
        "server.engines.opencode.auth.callbacks.antigravity_local_callback_server.stop",
        _fake_antigravity_listener_stop,
    )

    class _TokenPayload:
        access_token = "google-access"
        refresh_token = "google-refresh"
        expires_in = 3600
        email = "google@example.com"

    monkeypatch.setattr(
        manager._opencode_google_antigravity_oauth_proxy_flow,
        "_exchange_code",
        lambda **_kwargs: _TokenPayload(),
    )
    started = manager.start_session(
        "opencode",
        "auth",
        provider_id="google",
        transport="oauth_proxy",
        auth_method="auth_code_or_url",
    )
    assert started["engine"] == "opencode"
    assert started["provider_id"] == "google"
    assert started["transport"] == "oauth_proxy"
    assert started["status"] == "waiting_user"
    assert started["execution_mode"] == "protocol_proxy"
    assert "accounts.google.com/o/oauth2/v2/auth" in str(started["auth_url"])

    runtime = manager._sessions[started["session_id"]].driver_state  # noqa: SLF001
    assert isinstance(runtime, OpencodeGoogleAntigravityOAuthProxySession)
    submitted = manager.input_session(
        started["session_id"],
        "text",
        f"http://localhost:51121/oauth-callback?code=google-code&state={runtime.state}",
    )
    assert submitted["status"] == "succeeded"
    assert submitted["manual_fallback_used"] is True
    assert submitted["audit"]["callback_mode"] == "manual"
    assert submitted["audit"]["google_antigravity_single_account_written"] is True
    assert listener_calls["start"] == 0
    assert listener_calls["stop"] == 1

    accounts_path = profile.agent_home / ".config" / "opencode" / "antigravity-accounts.json"
    assert accounts_path.exists()


def test_engine_auth_flow_manager_opencode_google_oauth_proxy_rejects_device_auth(tmp_path: Path):
    command_path = _write_script(tmp_path / "fake-opencode-google", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )
    try:
        manager.start_session(
            "opencode",
            "auth",
            provider_id="google",
            transport="oauth_proxy",
            auth_method="api_key",
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "callback or auth_code_or_url" in str(exc)


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

    started = manager.start_session(
        "opencode",
        "auth",
        provider_id="google",
        transport="cli_delegate",
        auth_method="auth_code_or_url",
    )
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


def test_engine_auth_flow_manager_codex_oauth_proxy_device_start_failure_message(tmp_path: Path, monkeypatch):
    command_path = _write_script(tmp_path / "fake-codex", "exit 0")
    profile = _FakeProfile(tmp_path)
    manager = EngineAuthFlowManager(
        agent_manager=_FakeCliManager(profile, command_path),
        interaction_gate=EngineInteractionGate(),
        trust_manager=_TrustSpy(),
    )

    def _raise(*args, **kwargs):  # noqa: ANN002, ANN003
        raise OpenAIOAuthError("cf route blocked", status_code=530)

    monkeypatch.setattr(manager._openai_device_proxy_flow, "start_session", _raise)
    try:
        manager.start_session(
            "codex",
            "auth",
            auth_method="auth_code_or_url",
            transport="oauth_proxy",
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "HTTP 530" in str(exc)
        assert "callback / cli_delegate" in str(exc)
