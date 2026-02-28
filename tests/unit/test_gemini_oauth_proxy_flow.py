from datetime import datetime, timezone
from pathlib import Path

from server.engines.gemini.auth.protocol.oauth_proxy_flow import GeminiOAuthProxyError, GeminiOAuthProxyFlow


def _set_google_oauth_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "SKILL_RUNNER_GEMINI_OAUTH_CLIENT_ID",
        "test-gemini-client-id.apps.googleusercontent.com",
    )
    monkeypatch.setenv(
        "SKILL_RUNNER_GEMINI_OAUTH_CLIENT_SECRET",
        "test-gemini-client-secret",
    )


def test_gemini_oauth_proxy_flow_start_session(tmp_path: Path, monkeypatch):
    _set_google_oauth_env(monkeypatch)
    flow = GeminiOAuthProxyFlow(tmp_path)
    runtime = flow.start_session(
        session_id="g-session-1",
        callback_url="http://localhost:51122/oauth2callback",
        now=datetime.now(timezone.utc),
    )
    assert runtime.session_id == "g-session-1"
    assert runtime.redirect_uri == "http://localhost:51122/oauth2callback"
    assert runtime.state
    assert runtime.code_verifier
    assert runtime.auth_url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A51122%2Foauth2callback" in runtime.auth_url
    assert "code_challenge_method=S256" in runtime.auth_url


def test_gemini_oauth_proxy_flow_submit_input_writes_oauth_files(tmp_path: Path, monkeypatch):
    _set_google_oauth_env(monkeypatch)
    flow = GeminiOAuthProxyFlow(tmp_path)
    runtime = flow.start_session(
        session_id="g-session-2",
        callback_url="http://localhost:51122/oauth2callback",
        now=datetime.now(timezone.utc),
    )

    class _TokenPayload:
        access_token = "access-token"
        refresh_token = "refresh-token"
        token_type = "Bearer"
        scope = "openid profile email"
        id_token = "id-token"
        expires_in = 3600

    monkeypatch.setattr(flow, "_exchange_code", lambda **_kwargs: _TokenPayload())
    monkeypatch.setattr(flow, "_fetch_email", lambda _token: "gemini@example.com")

    mcp_tokens_path = tmp_path / ".gemini" / "mcp-oauth-tokens-v2.json"
    mcp_tokens_path.parent.mkdir(parents=True, exist_ok=True)
    mcp_tokens_path.write_text("not-a-json-payload", encoding="utf-8")

    result = flow.submit_input(
        runtime,
        f"http://localhost:51122/oauth2callback?code=abc123&state={runtime.state}",
    )
    assert result["google_account_email"] == "gemini@example.com"

    oauth_creds = flow.oauth_creds_path
    assert oauth_creds.exists()
    oauth_payload = oauth_creds.read_text(encoding="utf-8")
    assert '"access_token": "access-token"' in oauth_payload
    assert '"refresh_token": "refresh-token"' in oauth_payload

    google_accounts = flow.google_accounts_path
    assert google_accounts.exists()
    account_payload = google_accounts.read_text(encoding="utf-8")
    assert '"active": "gemini@example.com"' in account_payload

    assert mcp_tokens_path.read_text(encoding="utf-8") == "not-a-json-payload"


def test_gemini_oauth_proxy_flow_rejects_state_mismatch(tmp_path: Path, monkeypatch):
    _set_google_oauth_env(monkeypatch)
    flow = GeminiOAuthProxyFlow(tmp_path)
    runtime = flow.start_session(
        session_id="g-session-3",
        callback_url="http://localhost:51122/oauth2callback",
        now=datetime.now(timezone.utc),
    )
    try:
        flow.submit_input(
            runtime,
            "http://localhost:51122/oauth2callback?code=abc123&state=other-state",
        )
        raise AssertionError("expected GeminiOAuthProxyError")
    except GeminiOAuthProxyError as exc:
        assert "state mismatch" in str(exc).lower()
