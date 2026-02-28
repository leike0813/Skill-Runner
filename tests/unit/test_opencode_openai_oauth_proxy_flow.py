from datetime import datetime, timezone
from pathlib import Path

from server.engines.common.openai_auth import OpenAITokenSet
from server.engines.opencode.auth.protocol.openai_oauth_proxy_flow import OpencodeOpenAIOAuthProxyFlow


def test_opencode_openai_oauth_proxy_flow_start_and_submit(tmp_path: Path, monkeypatch):
    agent_home = tmp_path / "agent-home"
    flow = OpencodeOpenAIOAuthProxyFlow(agent_home)

    runtime = flow.start_session(
        session_id="s-1",
        callback_url="http://localhost:1455/auth/callback",
        now=datetime.now(timezone.utc),
    )
    assert runtime.auth_url.startswith("https://auth.openai.com/oauth/authorize?")
    assert "originator=opencode" in runtime.auth_url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A1455%2Fauth%2Fcallback" in runtime.auth_url

    monkeypatch.setattr(
        "server.engines.opencode.auth.protocol.openai_oauth_proxy_flow.exchange_authorization_code",
        lambda **_kwargs: OpenAITokenSet(
            id_token="a.b.c",
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=3600,
        ),
    )
    monkeypatch.setattr(
        "server.engines.opencode.auth.protocol.openai_oauth_proxy_flow.extract_account_id_from_id_token",
        lambda _id_token: "acct_123",
    )

    flow.submit_input(runtime, "abc123")
    auth_path = agent_home / ".local" / "share" / "opencode" / "auth.json"
    assert auth_path.exists()
    payload = auth_path.read_text(encoding="utf-8")
    assert '"openai"' in payload
    assert '"type": "oauth"' in payload
    assert '"accountId": "acct_123"' in payload
