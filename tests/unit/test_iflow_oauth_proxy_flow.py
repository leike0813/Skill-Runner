from datetime import datetime, timezone
from pathlib import Path

from server.services.iflow_oauth_proxy_flow import IFlowOAuthProxyError, IFlowOAuthProxyFlow


def test_iflow_oauth_proxy_flow_start_session(tmp_path: Path):
    flow = IFlowOAuthProxyFlow(tmp_path)
    runtime = flow.start_session(
        session_id="iflow-session-1",
        callback_url="http://localhost:11451/oauth2callback",
        auth_method="callback",
        now=datetime.now(timezone.utc),
    )
    assert runtime.session_id == "iflow-session-1"
    assert runtime.redirect_uri == "http://localhost:11451/oauth2callback"
    assert runtime.state
    assert runtime.auth_url.startswith("https://iflow.cn/oauth?")
    assert "redirect=http%3A%2F%2Flocalhost%3A11451%2Foauth2callback" in runtime.auth_url


def test_iflow_oauth_proxy_flow_submit_input_writes_iflow_files(tmp_path: Path, monkeypatch):
    flow = IFlowOAuthProxyFlow(tmp_path)
    runtime = flow.start_session(
        session_id="iflow-session-2",
        callback_url="http://localhost:11451/oauth2callback",
        auth_method="auth_code_or_url",
        now=datetime.now(timezone.utc),
    )

    class _TokenPayload:
        access_token = "iflow-access"
        refresh_token = "iflow-refresh"
        expires_in = 3600
        token_type = "Bearer"
        scope = "openid"

    monkeypatch.setattr(flow, "_exchange_code", lambda **_kwargs: _TokenPayload())
    monkeypatch.setattr(
        flow,
        "_fetch_user_info",
        lambda _access_token: {
            "apiKey": "iflow-sk-123",
            "userId": "u-1",
            "userName": "iflow-user",
            "avatar": "https://example.com/avatar.png",
            "email": "iflow@example.com",
            "phone": "13800000000",
        },
    )

    result = flow.submit_input(
        runtime,
        f"http://localhost:11451/oauth2callback?code=iflow-code&state={runtime.state}",
    )
    assert result["iflow_api_key_present"] is True
    assert result["iflow_user_name"] == "iflow-user"

    oauth_creds = flow.oauth_creds_path.read_text(encoding="utf-8")
    assert '"access_token": "iflow-access"' in oauth_creds
    assert '"refresh_token": "iflow-refresh"' in oauth_creds
    assert '"apiKey": "iflow-sk-123"' in oauth_creds

    iflow_accounts = flow.iflow_accounts_path.read_text(encoding="utf-8")
    assert '"iflowApiKey": "iflow-sk-123"' in iflow_accounts

    settings_payload = flow.settings_path.read_text(encoding="utf-8")
    assert '"selectedAuthType": "oauth-iflow"' in settings_payload
    assert '"baseUrl": "https://apis.iflow.cn/v1"' in settings_payload


def test_iflow_oauth_proxy_flow_rejects_state_mismatch(tmp_path: Path):
    flow = IFlowOAuthProxyFlow(tmp_path)
    runtime = flow.start_session(
        session_id="iflow-session-3",
        callback_url="http://localhost:11451/oauth2callback",
        auth_method="callback",
        now=datetime.now(timezone.utc),
    )
    try:
        flow.submit_input(
            runtime,
            "http://localhost:11451/oauth2callback?code=iflow-code&state=wrong-state",
        )
        raise AssertionError("expected IFlowOAuthProxyError")
    except IFlowOAuthProxyError as exc:
        assert "state mismatch" in str(exc).lower()
