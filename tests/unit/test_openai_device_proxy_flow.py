from datetime import datetime, timedelta, timezone

from server.engines.common.openai_auth.device_flow import OpenAIDeviceProxyFlow, OpenAIDeviceProxySession
from server.engines.common.openai_auth.common import (
    OpenAIDeviceAuthorizationCode,
    OpenAIDeviceCodeStart,
    OpenAITokenSet,
)


def test_openai_device_proxy_flow_start_session(monkeypatch):
    now = datetime(2026, 2, 27, 12, 0, 0, tzinfo=timezone.utc)

    def _fake_start(*, issuer, client_id, user_agent):  # noqa: ANN001
        assert issuer == "https://auth.openai.com"
        assert client_id == "client-1"
        assert user_agent == "ua-test"
        return OpenAIDeviceCodeStart(
            device_auth_id="dev-1",
            user_code="ABCD-EFGH",
            interval_seconds=5,
            verification_url="https://auth.openai.com/activate",
        )

    monkeypatch.setattr("server.engines.common.openai_auth.device_flow.request_openai_device_code", _fake_start)
    flow = OpenAIDeviceProxyFlow()
    runtime = flow.start_session(
        session_id="s-1",
        now=now,
        issuer="https://auth.openai.com",
        client_id="client-1",
        user_agent="ua-test",
    )
    assert runtime.session_id == "s-1"
    assert runtime.device_auth_id == "dev-1"
    assert runtime.user_code == "ABCD-EFGH"
    assert runtime.verification_url == "https://auth.openai.com/activate"
    assert runtime.next_poll_at == now + timedelta(seconds=5)
    assert runtime.completed is False


def test_openai_device_proxy_flow_poll_once_completes(monkeypatch):
    base = datetime(2026, 2, 27, 12, 0, 0, tzinfo=timezone.utc)
    runtime = OpenAIDeviceProxySession(
        session_id="s-2",
        issuer="https://auth.openai.com",
        client_id="app",
        redirect_uri="https://auth.openai.com/deviceauth/callback",
        device_auth_id="dev-2",
        user_code="CODE-1",
        verification_url="https://auth.openai.com/activate",
        interval_seconds=3,
        user_agent="ua-test",
        created_at=base,
        updated_at=base,
        last_poll_at=None,
        next_poll_at=base,
        completed=False,
    )

    def _fake_poll(*, device_auth_id, user_code, issuer, user_agent):  # noqa: ANN001
        assert device_auth_id == "dev-2"
        assert user_code == "CODE-1"
        assert issuer == "https://auth.openai.com"
        assert user_agent == "ua-test"
        return OpenAIDeviceAuthorizationCode(
            authorization_code="auth-code",
            code_verifier="verifier",
        )

    def _fake_exchange(*, code, redirect_uri, code_verifier, issuer, client_id):  # noqa: ANN001
        assert code == "auth-code"
        assert redirect_uri == "https://auth.openai.com/deviceauth/callback"
        assert code_verifier == "verifier"
        assert issuer == "https://auth.openai.com"
        assert client_id == "app"
        return OpenAITokenSet(
            id_token="id-token",
            access_token="access-token",
            refresh_token="refresh-token",
            expires_in=3600,
        )

    monkeypatch.setattr(
        "server.engines.common.openai_auth.device_flow.poll_openai_device_authorization_code",
        _fake_poll,
    )
    monkeypatch.setattr(
        "server.engines.common.openai_auth.device_flow.exchange_authorization_code",
        _fake_exchange,
    )

    flow = OpenAIDeviceProxyFlow()
    token_set = flow.poll_once(runtime, now=base + timedelta(seconds=3))
    assert token_set is not None
    assert token_set.access_token == "access-token"
    assert runtime.completed is True
    assert runtime.last_poll_at == base + timedelta(seconds=3)
