from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from email.message import Message
from pathlib import Path
from typing import Any, cast
from urllib import error as urllib_error
from urllib import parse as urllib_parse

import pytest

from server.engines.qwen.auth.protocol.qwen_oauth_proxy_flow import QwenOAuthProxyFlow, QwenOAuthSession


class _StubResponse:
    def __init__(self, body: str, *, status: int = 200) -> None:
        self._body = body.encode("utf-8")
        self.status = status

    def __enter__(self) -> "_StubResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None

    def read(self) -> bytes:
        return self._body


class _StubHTTPError(urllib_error.HTTPError):
    def __init__(self, url: str, code: int, msg: str, body: str) -> None:
        super().__init__(url, code, msg, hdrs=Message(), fp=None)
        self._body = body.encode("utf-8")

    def read(self, n: int = -1) -> bytes:
        return self._body


def test_qwen_oauth_proxy_flow_start_session_uses_pkce(tmp_path: Path, monkeypatch) -> None:
    flow = QwenOAuthProxyFlow(tmp_path)
    captured: dict[str, object] = {}

    def _fake_urlopen(request, timeout=30):  # noqa: ANN001
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = request.data.decode("utf-8")
        captured["headers"] = dict(request.header_items())
        return _StubResponse(
            json.dumps(
                {
                    "device_code": "device-1",
                    "user_code": "TEST123",
                    "verification_uri_complete": "https://chat.qwen.ai/device?user_code=TEST123",
                    "expires_in": 300,
                }
            )
        )

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    runtime = flow.start_session(
        session_id="qwen-session-1",
        now=datetime.now(timezone.utc),
    )

    body = urllib_parse.parse_qs(str(captured["body"]))
    assert captured["url"] == flow.AUTHORIZE_ENDPOINT
    assert captured["timeout"] == 30
    assert body["client_id"] == [flow.CLIENT_ID]
    assert body["scope"] == [flow.SCOPE]
    assert body["code_challenge_method"] == ["S256"]
    assert body["code_challenge"][0]
    raw_headers = cast(dict[str, str], captured["headers"])
    headers = {key.lower(): value for key, value in raw_headers.items()}
    assert headers["user-agent"].startswith("QwenCode/")
    assert headers["accept-language"] == "en-US,en;q=0.9"
    assert headers["x-request-id"]
    assert runtime.code_verifier
    assert runtime.user_code == "TEST123"


def test_qwen_oauth_proxy_flow_start_session_reports_empty_body(tmp_path: Path, monkeypatch) -> None:
    flow = QwenOAuthProxyFlow(tmp_path)

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout=30: _StubResponse("", status=200))

    with pytest.raises(RuntimeError, match=r"empty response body \(status=200\)"):
        flow.start_session(
            session_id="qwen-session-2",
            now=datetime.now(timezone.utc),
        )


def test_qwen_oauth_proxy_flow_start_session_reports_waf_block(tmp_path: Path, monkeypatch) -> None:
    flow = QwenOAuthProxyFlow(tmp_path)
    waf_html = '<!doctypehtml><meta charset="UTF-8"><meta name="aliyun_waf_aa" content="blocked">'

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout=30: _StubResponse(waf_html, status=200))

    with pytest.raises(RuntimeError, match=r"appears blocked by upstream WAF"):
        flow.start_session(
            session_id="qwen-session-waf",
            now=datetime.now(timezone.utc),
        )


def test_qwen_oauth_proxy_flow_start_session_wraps_url_error(tmp_path: Path, monkeypatch) -> None:
    flow = QwenOAuthProxyFlow(tmp_path)

    def _fake_urlopen(request, timeout=30):  # noqa: ANN001
        raise urllib_error.URLError("network down")

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    with pytest.raises(RuntimeError, match=r"Failed to request Qwen device code: .*network down"):
        flow.start_session(
            session_id="qwen-session-urlerror",
            now=datetime.now(timezone.utc),
        )


def test_qwen_oauth_proxy_flow_poll_once_sends_code_verifier(tmp_path: Path, monkeypatch) -> None:
    flow = QwenOAuthProxyFlow(tmp_path)
    now = datetime.now(timezone.utc)
    runtime = QwenOAuthSession(
        session_id="qwen-session-3",
        device_code="device-3",
        user_code="TEST999",
        verification_uri_complete="https://chat.qwen.ai/device?user_code=TEST999",
        code_verifier="verifier-3",
        expires_in=300,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=5),
        polling_started=True,
        next_poll_at=now,
    )
    captured: dict[str, str] = {}

    def _fake_urlopen(request, timeout=30):  # noqa: ANN001
        captured["body"] = request.data.decode("utf-8")
        captured["headers"] = dict(request.header_items())
        return _StubResponse(
            json.dumps(
                {
                    "access_token": "access-1",
                    "refresh_token": "refresh-1",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                }
            )
        )

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    completed = flow.poll_once(runtime, now=now)

    body = urllib_parse.parse_qs(captured["body"])
    assert completed is True
    assert body["device_code"] == ["device-3"]
    assert body["code_verifier"] == ["verifier-3"]
    raw_headers = cast(dict[str, str], captured["headers"])
    headers = {key.lower(): value for key, value in raw_headers.items()}
    assert headers["user-agent"].startswith("QwenCode/")
    assert headers["accept-language"] == "en-US,en;q=0.9"
    assert headers["x-request-id"]
    credentials = (tmp_path / ".qwen" / "oauth_creds.json").read_text(encoding="utf-8")
    assert '"access_token": "access-1"' in credentials


def test_qwen_oauth_proxy_flow_poll_once_handles_authorization_pending(tmp_path: Path, monkeypatch) -> None:
    flow = QwenOAuthProxyFlow(tmp_path)
    now = datetime.now(timezone.utc)
    runtime = QwenOAuthSession(
        session_id="qwen-session-pending",
        device_code="device-pending",
        user_code="PENDING123",
        verification_uri_complete="https://chat.qwen.ai/device?user_code=PENDING123",
        code_verifier="verifier-pending",
        expires_in=300,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=5),
        polling_started=True,
        next_poll_at=now,
    )

    def _fake_urlopen(request, timeout=30):  # noqa: ANN001
        raise _StubHTTPError(
            request.full_url,
            400,
            "Bad Request",
            json.dumps(
                {
                    "error": "authorization_pending",
                    "error_description": "Still waiting for the user to authorize",
                }
            ),
        )

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    completed = flow.poll_once(runtime, now=now)

    assert completed is False
    assert runtime.completed is False
    assert runtime.last_poll_result == "authorization_pending"
    assert not (tmp_path / ".qwen" / "oauth_creds.json").exists()


def test_qwen_oauth_proxy_flow_poll_once_handles_slow_down_http_429(tmp_path: Path, monkeypatch) -> None:
    flow = QwenOAuthProxyFlow(tmp_path)
    now = datetime.now(timezone.utc)
    runtime = QwenOAuthSession(
        session_id="qwen-session-slow",
        device_code="device-slow",
        user_code="SLOW123",
        verification_uri_complete="https://chat.qwen.ai/device?user_code=SLOW123",
        code_verifier="verifier-slow",
        expires_in=300,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=5),
        polling_started=True,
        next_poll_at=now,
    )

    def _fake_urlopen(request, timeout=30):  # noqa: ANN001
        raise _StubHTTPError(
            request.full_url,
            429,
            "Too Many Requests",
            json.dumps(
                {
                    "error": "slow_down",
                    "error_description": "Slow down polling frequency",
                }
            ),
        )

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    completed = flow.poll_once(runtime, now=now)

    assert completed is False
    assert runtime.last_poll_result == "slow_down"
    assert runtime.next_poll_at == now + timedelta(seconds=flow.POLL_INTERVAL_SECONDS * 2)


def test_qwen_oauth_proxy_flow_poll_once_rejects_success_without_access_token(tmp_path: Path, monkeypatch) -> None:
    flow = QwenOAuthProxyFlow(tmp_path)
    now = datetime.now(timezone.utc)
    runtime = QwenOAuthSession(
        session_id="qwen-session-invalid-success",
        device_code="device-invalid",
        user_code="INVALID123",
        verification_uri_complete="https://chat.qwen.ai/device?user_code=INVALID123",
        code_verifier="verifier-invalid",
        expires_in=300,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=5),
        polling_started=True,
        next_poll_at=now,
    )

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=30: _StubResponse(
            json.dumps(
                {
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "resource_url": "https://resource.example.test",
                }
            )
        ),
    )

    with pytest.raises(RuntimeError, match="missing access_token"):
        flow.poll_once(runtime, now=now)

    assert runtime.completed is False
    assert runtime.last_poll_result == "failed"
    assert runtime.last_poll_error == "missing_access_token"
    assert not (tmp_path / ".qwen" / "oauth_creds.json").exists()


def test_qwen_oauth_proxy_flow_poll_once_persists_resource_url(tmp_path: Path, monkeypatch) -> None:
    flow = QwenOAuthProxyFlow(tmp_path)
    now = datetime.now(timezone.utc)
    runtime = QwenOAuthSession(
        session_id="qwen-session-resource",
        device_code="device-resource",
        user_code="RESOURCE123",
        verification_uri_complete="https://chat.qwen.ai/device?user_code=RESOURCE123",
        code_verifier="verifier-resource",
        expires_in=300,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=5),
        polling_started=True,
        next_poll_at=now,
    )

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout=30: _StubResponse(
            json.dumps(
                {
                    "access_token": "access-resource",
                    "refresh_token": "refresh-resource",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "resource_url": "https://resource.example.test",
                }
            )
        ),
    )

    completed = flow.poll_once(runtime, now=now)

    assert completed is True
    credentials = json.loads((tmp_path / ".qwen" / "oauth_creds.json").read_text(encoding="utf-8"))
    assert credentials["resource_url"] == "https://resource.example.test"


def test_qwen_oauth_proxy_flow_poll_once_wraps_url_error(tmp_path: Path, monkeypatch) -> None:
    flow = QwenOAuthProxyFlow(tmp_path)
    now = datetime.now(timezone.utc)
    runtime = QwenOAuthSession(
        session_id="qwen-session-urlerror-poll",
        device_code="device-urlerror",
        user_code="URLERR123",
        verification_uri_complete="https://chat.qwen.ai/device?user_code=URLERR123",
        code_verifier="verifier-urlerror",
        expires_in=300,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=5),
        polling_started=True,
        next_poll_at=now,
    )

    def _fake_urlopen(request, timeout=30):  # noqa: ANN001
        raise urllib_error.URLError("token network down")

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    with pytest.raises(RuntimeError, match=r"Token request failed: .*token network down"):
        flow.poll_once(runtime, now=now)

    assert runtime.completed is False
    assert runtime.last_poll_result == "failed"
    assert runtime.last_poll_error is not None
