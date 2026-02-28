from pathlib import Path
from datetime import datetime, timezone

from server.engines.codex.auth.protocol.oauth_proxy_flow import CodexOAuthProxyFlow
from server.engines.common.openai_auth import OpenAITokenSet


def test_codex_oauth_proxy_flow_start_and_submit(tmp_path: Path, monkeypatch):
    agent_home = tmp_path / "agent-home"
    flow = CodexOAuthProxyFlow(agent_home)

    runtime = flow.start_session(
        session_id="s-1",
        callback_url="http://localhost:1455/auth/callback",
        now=datetime.now(timezone.utc),
    )
    assert runtime.auth_url.startswith("https://auth.openai.com/oauth/authorize?")
    assert "originator=codex_cli_rs" in runtime.auth_url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A1455%2Fauth%2Fcallback" in runtime.auth_url

    monkeypatch.setattr(
        "server.engines.codex.auth.protocol.oauth_proxy_flow.exchange_authorization_code",
        lambda **_kwargs: OpenAITokenSet(
            id_token="a.b.c",
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=3600,
        ),
    )
    monkeypatch.setattr(
        "server.engines.codex.auth.protocol.oauth_proxy_flow.exchange_id_token_for_api_key",
        lambda **_kwargs: "sk-proxy-api-key",
    )

    flow.submit_input(runtime, "http://localhost:1455/auth/callback?code=abc123")
    auth_path = agent_home / ".codex" / "auth.json"
    assert auth_path.exists()
    payload = auth_path.read_text(encoding="utf-8")
    assert '"OPENAI_API_KEY": "sk-proxy-api-key"' in payload
    assert '"access_token": "access-token"' in payload
