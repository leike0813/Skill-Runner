from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import pytest

from server.engines.codebuddy.auth.credential_store import CodeBuddyCredentialStore
from server.engines.codebuddy.auth.runtime_handler import CodeBuddyAuthRuntimeHandler
from server.engines.codebuddy.auth.sdk_auth_flow import CodeBuddySdkAuthFlow


def _popen_factory(source: str) -> Callable[..., subprocess.Popen[str]]:
    def _spawn(_command: list[str], **kwargs: Any) -> subprocess.Popen[str]:
        return subprocess.Popen([sys.executable, "-u", "-c", source], **kwargs)

    return _spawn


def _flow(
    tmp_path: Path,
    source: str,
    *,
    on_success: Callable[[str], None] | None = None,
) -> CodeBuddySdkAuthFlow:
    store = CodeBuddyCredentialStore(
        path=tmp_path / "data" / "engine_credentials" / "codebuddy.json",
        agent_home=tmp_path / "agent-home",
    )
    return CodeBuddySdkAuthFlow(
        credential_store=store,
        on_success=on_success,
        popen_factory=_popen_factory(source),
    )


def _poll_until_terminal(flow: CodeBuddySdkAuthFlow, session: Any) -> str:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        state = flow.poll(session)
        if state != "waiting_user":
            return state
        time.sleep(0.01)
    raise AssertionError("auth flow did not finish")


def test_sdk_flow_returns_url_then_commits_credential_in_memory(tmp_path: Path) -> None:
    source = (
        "import json,time\n"
        "print(json.dumps({'type':'auth_url','auth_url':'https://auth.example/login'}), flush=True)\n"
        "time.sleep(0.05)\n"
        "print(json.dumps({'type':'credential','token':'secret-token','user_id':'user-1'}), flush=True)\n"
    )
    refreshed: list[str] = []
    flow = _flow(tmp_path, source, on_success=refreshed.append)
    session = flow.start(
        provider_id="codebuddy-cn",
        codebuddy_path=Path("/managed/codebuddy"),
        timeout=10,
    )
    temp_root = session.temp_root

    assert session.auth_url == "https://auth.example/login"
    assert not hasattr(session, "token")
    assert _poll_until_terminal(flow, session) == "succeeded"
    assert flow.credential_store.get("codebuddy-cn").token == "secret-token"  # type: ignore[union-attr]
    assert refreshed == ["codebuddy-cn"]
    assert not temp_root.exists()


def test_sdk_flow_routes_global_environment_in_worker_command(tmp_path: Path) -> None:
    captured: list[list[str]] = []
    source = (
        "import json,time\n"
        "print(json.dumps({'type':'auth_url','auth_url':'https://auth.example/global'}), flush=True)\n"
        "time.sleep(10)\n"
    )

    def _capture(command: list[str], **kwargs: Any) -> subprocess.Popen[str]:
        captured.append(command)
        return subprocess.Popen([sys.executable, "-u", "-c", source], **kwargs)

    store = CodeBuddyCredentialStore(
        path=tmp_path / "vault.json",
        agent_home=tmp_path / "agent-home",
    )
    flow = CodeBuddySdkAuthFlow(credential_store=store, popen_factory=_capture)
    session = flow.start(
        provider_id="codebuddy-global",
        codebuddy_path=Path("/managed/codebuddy"),
        timeout=10,
    )
    try:
        environment_index = captured[0].index("--environment") + 1
        assert captured[0][environment_index] == "public"
    finally:
        flow.cancel(session)


def test_worker_environment_does_not_inherit_codebuddy_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEBUDDY_AUTH_TOKEN", "host-token")
    monkeypatch.setenv("CODEBUDDY_API_KEY", "host-key")
    monkeypatch.setenv("CODEBUDDY_BASE_URL", "https://host.example")
    env = CodeBuddySdkAuthFlow.build_worker_environment(tmp_path)

    assert "CODEBUDDY_AUTH_TOKEN" not in env
    assert "CODEBUDDY_API_KEY" not in env
    assert "CODEBUDDY_BASE_URL" not in env
    assert env["CODEBUDDY_CONFIG_DIR"] == str(tmp_path / "config")
    assert env["HOME"] == str(tmp_path / "home")


def test_sdk_flow_failure_is_redacted_and_cleans_temp(tmp_path: Path) -> None:
    source = (
        "import json,time\n"
        "print(json.dumps({'type':'auth_url','auth_url':'https://auth.example/login'}), flush=True)\n"
        "print(json.dumps({'type':'error','error':'token=very-secret failed'}), flush=True)\n"
        "time.sleep(10)\n"
    )
    flow = _flow(tmp_path, source)
    session = flow.start(
        provider_id="codebuddy-cn",
        codebuddy_path=Path("/managed/codebuddy"),
        timeout=10,
    )
    temp_root = session.temp_root

    with pytest.raises(RuntimeError) as exc_info:
        _poll_until_terminal(flow, session)
    assert "very-secret" not in str(exc_info.value)
    assert "[REDACTED]" in str(exc_info.value)
    assert not temp_root.exists()


def test_sdk_flow_start_timeout_terminates_worker_and_cleans_temp(tmp_path: Path) -> None:
    flow = _flow(tmp_path, "import time; time.sleep(10)")
    before = set(Path("/tmp").glob("codebuddy-auth-codebuddy-cn-*"))

    with pytest.raises(TimeoutError):
        flow.start(
            provider_id="codebuddy-cn",
            codebuddy_path=Path("/managed/codebuddy"),
            timeout=10,
            startup_timeout=0.05,
        )

    after = set(Path("/tmp").glob("codebuddy-auth-codebuddy-cn-*"))
    assert after == before


def test_sdk_flow_cancel_terminates_worker_and_cleans_temp(tmp_path: Path) -> None:
    source = (
        "import json,time\n"
        "print(json.dumps({'type':'auth_url','auth_url':'https://auth.example/login'}), flush=True)\n"
        "time.sleep(10)\n"
    )
    flow = _flow(tmp_path, source)
    session = flow.start(
        provider_id="codebuddy-cn",
        codebuddy_path=Path("/managed/codebuddy"),
        timeout=10,
    )
    temp_root = session.temp_root

    flow.cancel(session)

    assert session.process.poll() is not None
    assert not temp_root.exists()


class _DriverRegistry:
    def supports(self, **kwargs: Any) -> bool:
        return (
            kwargs["transport"] == "oauth_proxy"
            and kwargs["auth_method"] == "auth_code_or_url"
            and kwargs["provider_id"] in {"codebuddy-cn", "codebuddy-global"}
        )


def test_runtime_handler_requires_canonical_provider_and_managed_cli() -> None:
    handler = CodeBuddyAuthRuntimeHandler(manager=object())
    plan = handler.plan_start(
        method="auth",
        auth_method=None,
        transport="oauth_proxy",
        provider_id="codebuddy-global",
        driver_registry=_DriverRegistry(),
        resolve_engine_command=lambda engine: Path("/managed/codebuddy") if engine == "codebuddy" else None,
    )

    assert plan.provider_id == "codebuddy-global"
    assert plan.command == Path("/managed/codebuddy")
    with pytest.raises(ValueError):
        handler.plan_start(
            method="auth",
            auth_method=None,
            transport="oauth_proxy",
            provider_id="public",
            driver_registry=_DriverRegistry(),
            resolve_engine_command=lambda _engine: Path("/managed/codebuddy"),
        )
