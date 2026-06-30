from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from server.engines.qwen.auth.protocol.coding_plan_flow import CodingPlanSession
from server.engines.qwen.auth.runtime_handler import QwenAuthRuntimeHandler
from server.runtime.auth.session_lifecycle import AuthStartPlan, StartRuntimeContext


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _StubDriverRegistry:
    def supports(self, *, transport, engine, auth_method, provider_id=None):  # noqa: ANN001
        assert engine == "qwen"
        return transport == "oauth_proxy" and auth_method == "api_key" and provider_id is not None


class _StubManager:
    def __init__(self) -> None:
        self.finalized: list[str] = []
        self._qwen_coding_plan_flow = SimpleNamespace()

    def _new_session(self, **kwargs):  # noqa: ANN003
        return SimpleNamespace(**kwargs)

    def _finalize_active_session(self, session) -> None:  # noqa: ANN001
        self.finalized.append(session.session_id)


def _build_context(tmp_path: Path) -> StartRuntimeContext:
    now = _utc_now()
    return StartRuntimeContext(
        session_id="auth-qwen-1",
        session_dir=tmp_path,
        output_path=tmp_path / "auth.log",
        env={},
        now=now,
        expires_at=now + timedelta(minutes=15),
        cleanup_state={},
    )


def test_qwen_runtime_handler_plan_start_matches_api_key_contract(tmp_path: Path) -> None:
    handler = QwenAuthRuntimeHandler(_StubManager())
    plan = handler.plan_start(
        method="auth",
        auth_method="api_key",
        transport="oauth_proxy",
        provider_id="openrouter",
        driver_registry=_StubDriverRegistry(),
        resolve_engine_command=lambda _engine: tmp_path / "qwen",
    )

    assert isinstance(plan, AuthStartPlan)
    assert plan.engine == "qwen"
    assert plan.transport == "oauth_proxy"
    assert plan.provider_id == "openrouter"
    assert plan.auth_method == "api_key"
    assert plan.command is None
    assert plan.requires_command is False


def test_qwen_runtime_handler_rejects_removed_qwen_oauth(tmp_path: Path) -> None:
    handler = QwenAuthRuntimeHandler(_StubManager())

    with pytest.raises(ValueError, match="Unsupported qwen provider: qwen-oauth"):
        handler.plan_start(
            method="auth",
            auth_method="auth_code_or_url",
            transport="oauth_proxy",
            provider_id="qwen-oauth",
            driver_registry=_StubDriverRegistry(),
            resolve_engine_command=lambda _engine: tmp_path / "qwen",
        )


def test_qwen_runtime_handler_rejects_cli_delegate(tmp_path: Path) -> None:
    handler = QwenAuthRuntimeHandler(_StubManager())

    with pytest.raises(ValueError, match="qwen only supports oauth_proxy"):
        handler.plan_start(
            method="auth",
            auth_method="api_key",
            transport="cli_delegate",
            provider_id="coding-plan-global",
            driver_registry=_StubDriverRegistry(),
            resolve_engine_command=lambda _engine: tmp_path / "qwen",
        )


def test_qwen_runtime_handler_api_key_proxy_handles_input(tmp_path: Path) -> None:
    manager = _StubManager()
    runtime = CodingPlanSession(
        session_id="auth-qwen-1",
        provider_id="openrouter",
        region="",
    )
    manager._qwen_coding_plan_flow.start_session = lambda **_kwargs: runtime
    captured: dict[str, str] = {}

    def _complete_api_key(_runtime, value):  # noqa: ANN001
        captured["value"] = value

    manager._qwen_coding_plan_flow.complete_api_key = _complete_api_key
    handler = QwenAuthRuntimeHandler(manager)
    context = _build_context(tmp_path)
    plan = handler.plan_start(
        method="auth",
        auth_method="api_key",
        transport="oauth_proxy",
        provider_id="openrouter",
        driver_registry=_StubDriverRegistry(),
        resolve_engine_command=lambda _engine: None,
    )

    session = handler.start_session_locked(
        plan=plan,
        callback_base_url=None,
        context=context,
    )
    handler.refresh_session_locked(session)
    assert session.driver == "qwen_coding_plan_proxy"
    assert session.status == "waiting_user"
    assert session.input_kind == "api_key"

    handler.handle_input(session, "api_key", "sk-or-123")
    assert session.status == "succeeded"
    assert captured["value"] == "sk-or-123"
    assert manager.finalized == ["auth-qwen-1"]
