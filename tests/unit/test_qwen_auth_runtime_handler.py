from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from server.engines.qwen.auth.drivers.cli_delegate_flow import QwenAuthCliSession
from server.engines.qwen.auth.protocol.coding_plan_flow import CodingPlanSession
from server.engines.qwen.auth.protocol.qwen_oauth_proxy_flow import QwenOAuthSession
from server.engines.qwen.auth.runtime_handler import QwenAuthRuntimeHandler
from server.runtime.auth.session_lifecycle import AuthStartPlan, StartRuntimeContext


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _StubDriverRegistry:
    def supports(self, *, transport, engine, auth_method, provider_id=None):  # noqa: ANN001
        assert engine == "qwen"
        return True


class _StubManager:
    def __init__(self) -> None:
        self.finalized: list[str] = []
        self._qwen_oauth_proxy_flow = SimpleNamespace()
        self._qwen_coding_plan_flow = SimpleNamespace()
        self._qwen_flow = SimpleNamespace()

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


def test_qwen_runtime_handler_plan_start_matches_shared_contract(tmp_path: Path) -> None:
    handler = QwenAuthRuntimeHandler(_StubManager())
    command_path = tmp_path / "qwen"
    plan = handler.plan_start(
        method="auth",
        auth_method="auth_code_or_url",
        transport="cli_delegate",
        provider_id="qwen-oauth",
        driver_registry=_StubDriverRegistry(),
        resolve_engine_command=lambda _engine: command_path,
    )

    assert isinstance(plan, AuthStartPlan)
    assert plan.engine == "qwen"
    assert plan.transport == "cli_delegate"
    assert plan.provider_id == "qwen-oauth"
    assert plan.command == command_path


def test_qwen_runtime_handler_oauth_proxy_start_and_refresh_success(tmp_path: Path) -> None:
    manager = _StubManager()
    now = _utc_now()
    runtime = QwenOAuthSession(
        session_id="auth-qwen-1",
        device_code="device-1",
        user_code="TEST123",
        verification_uri_complete="https://chat.qwen.ai/device?user_code=TEST123",
        code_verifier="verifier-1",
        expires_in=300,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    manager._qwen_oauth_proxy_flow.start_session = lambda **_kwargs: runtime

    def _start_polling(_runtime, now=None, poll_now=False):  # noqa: ANN001
        current = now or _utc_now()
        _runtime.polling_started = True
        _runtime.next_poll_at = current if poll_now else (_runtime.next_poll_at or current + timedelta(seconds=2))

    def _poll_once(_runtime, now=None):  # noqa: ANN001
        current = now or _utc_now()
        next_poll_at = _runtime.next_poll_at
        if next_poll_at is not None and current < next_poll_at:
            return False
        return True

    manager._qwen_oauth_proxy_flow.start_polling = _start_polling
    manager._qwen_oauth_proxy_flow.submit_input = lambda _runtime, _value, now=None: setattr(_runtime, "polling_started", True)
    manager._qwen_oauth_proxy_flow.poll_once = _poll_once
    handler = QwenAuthRuntimeHandler(manager)
    context = _build_context(tmp_path)
    plan = handler.plan_start(
        method="auth",
        auth_method="auth_code_or_url",
        transport="oauth_proxy",
        provider_id="qwen-oauth",
        driver_registry=_StubDriverRegistry(),
        resolve_engine_command=lambda _engine: None,
    )

    session = handler.start_session_locked(
        plan=plan,
        callback_base_url=None,
        context=context,
    )
    assert session.driver == "qwen_oauth_proxy"
    assert session.input_kind is None

    handler.refresh_session_locked(session)
    assert session.status == "waiting_user"
    runtime.next_poll_at = _utc_now()
    handler.refresh_session_locked(session)
    assert session.status == "succeeded"
    assert manager.finalized == ["auth-qwen-1"]


def test_qwen_runtime_handler_coding_plan_cli_sets_api_key_input(tmp_path: Path) -> None:
    manager = _StubManager()
    now = _utc_now()

    class _FakeProcess:
        pid = 1234

        def poll(self):  # noqa: ANN201
            return None

    runtime = QwenAuthCliSession(
        session_id="auth-qwen-1",
        provider_id="coding-plan-global",
        process=cast(Any, _FakeProcess()),
        master_fd=0,
        output_path=tmp_path / "auth.log",
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=5),
        status="waiting_user",
        api_key_prompt_visible=True,
    )
    manager._qwen_flow.start_session = lambda **_kwargs: runtime
    manager._qwen_flow.refresh = lambda _runtime: None
    handler = QwenAuthRuntimeHandler(manager)
    context = _build_context(tmp_path)
    plan = handler.plan_start(
        method="auth",
        auth_method="api_key",
        transport="cli_delegate",
        provider_id="coding-plan-global",
        driver_registry=_StubDriverRegistry(),
        resolve_engine_command=lambda _engine: tmp_path / "qwen",
    )

    session = handler.start_session_locked(
        plan=plan,
        callback_base_url=None,
        context=context,
    )
    handler.refresh_session_locked(session)
    assert session.driver == "qwen"
    assert session.input_kind == "api_key"
    assert session.status == "waiting_user"


def test_qwen_runtime_handler_coding_plan_proxy_handles_api_key_input(tmp_path: Path) -> None:
    manager = _StubManager()
    runtime = CodingPlanSession(
        session_id="auth-qwen-1",
        provider_id="coding-plan-china",
        region="china",
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
        provider_id="coding-plan-china",
        driver_registry=_StubDriverRegistry(),
        resolve_engine_command=lambda _engine: None,
    )

    session = handler.start_session_locked(
        plan=plan,
        callback_base_url=None,
        context=context,
    )
    handler.refresh_session_locked(session)
    assert session.status == "waiting_user"
    assert session.input_kind == "api_key"

    handler.handle_input(session, "api_key", "sk-sp-123")
    assert session.status == "succeeded"
    assert captured["value"] == "sk-sp-123"
    assert manager.finalized == ["auth-qwen-1"]
