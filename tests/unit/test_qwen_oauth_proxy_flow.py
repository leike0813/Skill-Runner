from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast
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
