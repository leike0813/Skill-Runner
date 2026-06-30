from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from server.engines.kilo.auth import (
    KiloGatewayDeviceAuthFlow,
    KiloGatewayDeviceAuthSession,
)


class _FakeResponse:
    def __init__(self, *, status: int, payload: dict[str, Any] | None = None) -> None:
        self.status = status
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        if self._payload is None:
            return b""
        return json.dumps(self._payload).encode("utf-8")

    def getcode(self) -> int:
        return self.status


def _runtime(now: datetime) -> KiloGatewayDeviceAuthSession:
    return KiloGatewayDeviceAuthSession(
        session_id="auth-kilo",
        code="code-123",
        user_code="code-123",
        verification_url="https://app.kilo.ai/device",
        expires_in=600,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=10),
        polling_started=True,
        next_poll_at=now,
    )


def test_kilo_gateway_poll_pending_202_does_not_require_json_body(
    tmp_path: Path,
    monkeypatch,
) -> None:
    flow = KiloGatewayDeviceAuthFlow(tmp_path)
    now = datetime.now(timezone.utc)
    runtime = _runtime(now)
    monkeypatch.setattr(
        "server.engines.kilo.auth.protocol.kilo_gateway_device_auth_flow.urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(status=202),
    )

    completed = flow.poll_once(runtime, now=now)

    assert completed is False
    assert runtime.last_poll_result == "pending"
    assert not flow.auth_path.exists()


def test_kilo_gateway_poll_approved_writes_managed_kilo_auth_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    flow = KiloGatewayDeviceAuthFlow(tmp_path)
    now = datetime.now(timezone.utc)
    runtime = _runtime(now)
    monkeypatch.setattr(
        "server.engines.kilo.auth.protocol.kilo_gateway_device_auth_flow.urllib.request.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(
            status=200,
            payload={
                "status": "approved",
                "token": "kilo-token-123",
                "userEmail": "user@example.test",
            },
        ),
    )

    completed = flow.poll_once(runtime, now=now)

    assert completed is True
    assert runtime.last_poll_result == "succeeded"
    payload = json.loads(flow.auth_path.read_text(encoding="utf-8"))
    assert payload["kilo"] == {
        "type": "oauth",
        "access": "kilo-token-123",
        "refresh": "kilo-token-123",
        "expires": int((now + timedelta(days=365)).timestamp() * 1000),
        "accountId": "user@example.test",
    }
