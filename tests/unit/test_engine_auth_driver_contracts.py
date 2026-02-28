from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from server.runtime.auth.contracts import AuthDriverContext, AuthDriverResult


def test_auth_driver_context_is_frozen_and_carries_transport_fields() -> None:
    ctx = AuthDriverContext(
        transport="oauth_proxy",
        engine="codex",
        auth_method="callback",
        provider_id=None,
        method="auth",
        callback_base_url="http://localhost:8000",
        extra={"trace_id": "t1"},
    )

    assert ctx.transport == "oauth_proxy"
    assert ctx.engine == "codex"
    assert ctx.extra["trace_id"] == "t1"

    with pytest.raises(FrozenInstanceError):
        ctx.transport = "cli_delegate"  # type: ignore[misc]


def test_auth_driver_result_defaults_and_optional_fields() -> None:
    result = AuthDriverResult(status="waiting_user", auth_ready=False)
    assert result.status == "waiting_user"
    assert result.auth_ready is False
    assert result.auth_url is None
    assert result.input_kind is None

    with_details = AuthDriverResult(
        status="succeeded",
        auth_ready=True,
        auth_url="https://example.com/oauth",
        user_code="ABCD-EFGH",
        input_kind="text",
        audit={"callback_mode": "auto"},
    )
    assert with_details.user_code == "ABCD-EFGH"
    assert with_details.audit == {"callback_mode": "auto"}

