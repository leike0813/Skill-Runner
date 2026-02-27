import json
from datetime import datetime, timezone
from pathlib import Path

from server.services.opencode_google_antigravity_oauth_proxy_flow import (
    AntigravityOAuthProxyError,
    OpencodeGoogleAntigravityOAuthProxyFlow,
)


def _auth_paths(agent_home: Path) -> tuple[Path, Path]:
    auth_path = agent_home / ".local" / "share" / "opencode" / "auth.json"
    accounts_path = agent_home / ".config" / "opencode" / "antigravity-accounts.json"
    return auth_path, accounts_path


def _set_google_oauth_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "SKILL_RUNNER_OPENCODE_GOOGLE_OAUTH_CLIENT_ID",
        "test-opencode-google-client-id.apps.googleusercontent.com",
    )
    monkeypatch.setenv(
        "SKILL_RUNNER_OPENCODE_GOOGLE_OAUTH_CLIENT_SECRET",
        "test-opencode-google-client-secret",
    )


def test_opencode_google_antigravity_oauth_proxy_start_session(tmp_path: Path, monkeypatch):
    _set_google_oauth_env(monkeypatch)
    flow = OpencodeGoogleAntigravityOAuthProxyFlow(tmp_path)
    runtime = flow.start_session(
        session_id="session-1",
        now=datetime.now(timezone.utc),
    )
    assert runtime.session_id == "session-1"
    assert runtime.redirect_uri == "http://localhost:51121/oauth-callback"
    assert runtime.state
    assert runtime.code_verifier
    assert runtime.auth_url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A51121%2Foauth-callback" in runtime.auth_url
    assert "prompt=consent" in runtime.auth_url


def test_opencode_google_antigravity_oauth_proxy_submit_input_full_callback_url(tmp_path: Path, monkeypatch):
    _set_google_oauth_env(monkeypatch)
    flow = OpencodeGoogleAntigravityOAuthProxyFlow(tmp_path)
    runtime = flow.start_session(
        session_id="session-2",
        auth_method="auth_code_or_url",
        now=datetime.now(timezone.utc),
    )

    class _TokenPayload:
        access_token = "access-token"
        refresh_token = "refresh-token"
        expires_in = 3600
        email = "user@example.com"

    monkeypatch.setattr(flow, "_exchange_code", lambda **_kwargs: _TokenPayload())
    result = flow.submit_input(
        runtime,
        f"http://localhost:51121/oauth-callback?code=abc123&state={runtime.state}",
    )
    assert result["google_antigravity_single_account_written"] is True
    assert result["callback_mode"] == "manual"

    auth_path, accounts_path = _auth_paths(tmp_path)
    assert auth_path.exists()
    assert accounts_path.exists()

    auth_payload = json.loads(auth_path.read_text(encoding="utf-8"))
    google = auth_payload["google"]
    assert google["type"] == "oauth"
    assert google["refresh"] == "refresh-token|"
    assert google["access"] == "access-token"
    assert google["accountId"] == "user@example.com"
    assert int(google["expires"]) > 0

    accounts_payload = json.loads(accounts_path.read_text(encoding="utf-8"))
    assert accounts_payload["version"] == 4
    assert accounts_payload["activeIndex"] == 0
    assert accounts_payload["activeIndexByFamily"] == {"claude": 0, "gemini": 0}
    assert len(accounts_payload["accounts"]) == 1
    account = accounts_payload["accounts"][0]
    assert account["refreshToken"] == "refresh-token"
    assert account["enabled"] is True
    assert account["email"] == "user@example.com"


def test_opencode_google_antigravity_oauth_proxy_submit_input_rejects_state_mismatch(
    tmp_path: Path,
    monkeypatch,
):
    _set_google_oauth_env(monkeypatch)
    flow = OpencodeGoogleAntigravityOAuthProxyFlow(tmp_path)
    runtime = flow.start_session(
        session_id="session-3",
        now=datetime.now(timezone.utc),
    )
    try:
        flow.submit_input(
            runtime,
            "http://localhost:51121/oauth-callback?code=abc123&state=other-state",
        )
        raise AssertionError("expected AntigravityOAuthProxyError")
    except AntigravityOAuthProxyError as exc:
        assert "state mismatch" in str(exc)
