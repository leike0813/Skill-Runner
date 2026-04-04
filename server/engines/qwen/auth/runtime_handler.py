from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from server.runtime.auth.session_lifecycle import AuthStartPlan, StartRuntimeContext
from server.services.engine_management.engine_auth_strategy_service import (
    SessionBehaviorPolicy,
    engine_auth_strategy_service,
)
from server.services.engine_management.provider_aware_auth import get_engine_auth_provider

from .drivers.cli_delegate_flow import QwenAuthCliSession
from .protocol.coding_plan_flow import CodingPlanSession
from .protocol.qwen_oauth_proxy_flow import QwenOAuthSession

_DEFAULT_TRANSPORT = "oauth_proxy"
_AUTH_METHOD_AUTH_CODE_OR_URL = "auth_code_or_url"
_AUTH_METHOD_API_KEY = "api_key"
_TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "expired"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class QwenAuthRuntimeHandler:
    def __init__(self, manager: Any) -> None:
        self._manager = manager

    def requires_parent_trust_bootstrap(self) -> bool:
        return False

    def _session_behavior(
        self,
        *,
        transport: str,
        provider_id: str | None,
    ) -> SessionBehaviorPolicy:
        return engine_auth_strategy_service.runtime_session_behavior_for_transport(
            engine="qwen",
            transport=transport,
            provider_id=provider_id,
        )

    def plan_start(
        self,
        *,
        method: str,
        auth_method: str | None,
        transport: str,
        provider_id: str | None,
        driver_registry: Any,
        resolve_engine_command: Any,
    ) -> AuthStartPlan:
        provider = get_engine_auth_provider("qwen", provider_id)
        normalized_provider_id = provider.provider_id
        if normalized_provider_id == "qwen-oauth":
            if auth_method is None:
                effective_auth_method = _AUTH_METHOD_AUTH_CODE_OR_URL
            elif auth_method == _AUTH_METHOD_AUTH_CODE_OR_URL:
                effective_auth_method = auth_method
            else:
                raise ValueError("Unsupported auth_method for qwen-oauth: use auth_code_or_url")
        else:
            if auth_method is None:
                effective_auth_method = _AUTH_METHOD_API_KEY
            elif auth_method == _AUTH_METHOD_API_KEY:
                effective_auth_method = auth_method
            else:
                raise ValueError("Unsupported auth_method for Coding Plan: use api_key")

        if transport not in {_DEFAULT_TRANSPORT, "cli_delegate"}:
            raise ValueError("Unsupported transport combination: qwen only supports oauth_proxy|cli_delegate")
        if not driver_registry.supports(
            transport=transport,
            engine="qwen",
            auth_method=effective_auth_method,
            provider_id=normalized_provider_id,
        ):
            raise ValueError(
                "Unsupported auth combination: "
                f"transport={transport}, engine=qwen, auth_method={effective_auth_method}, "
                f"provider_id={normalized_provider_id}"
            )

        requires_command = transport == "cli_delegate"
        command = resolve_engine_command("qwen") if requires_command else None
        if requires_command and command is None:
            raise RuntimeError("qwen CLI not found")

        return AuthStartPlan(
            engine="qwen",
            method=method,
            auth_method=effective_auth_method,
            transport=transport,
            provider_id=normalized_provider_id,
            provider=provider,
            registry_provider_id=normalized_provider_id,
            command=command,
            requires_command=requires_command,
        )

    def start_session_locked(
        self,
        *,
        plan: AuthStartPlan,
        callback_base_url: str | None,
        context: StartRuntimeContext,
    ) -> Any:
        _ = callback_base_url
        provider = plan.provider
        assert provider is not None

        if plan.transport == _DEFAULT_TRANSPORT:
            if provider.provider_id == "qwen-oauth":
                behavior = self._session_behavior(
                    transport=plan.transport,
                    provider_id=provider.provider_id,
                )
                runtime = self._manager._qwen_oauth_proxy_flow.start_session(  # noqa: SLF001
                    session_id=context.session_id,
                    now=context.now,
                )
                if behavior.polling_start == "immediate":
                    self._manager._qwen_oauth_proxy_flow.start_polling(  # noqa: SLF001
                        runtime,
                        now=context.now,
                        poll_now=False,
                    )
                return self._manager._new_session(  # noqa: SLF001
                    session_id=context.session_id,
                    engine="qwen",
                    method=plan.method,
                    auth_method=plan.auth_method,
                    transport=plan.transport,
                    provider_id=provider.provider_id,
                    provider_name=provider.display_name,
                    created_at=context.now,
                    updated_at=context.now,
                    expires_at=context.expires_at,
                    status="starting",
                    input_kind="text" if behavior.input_required else None,
                    output_path=context.output_path,
                    process=None,
                    auth_url=runtime.verification_uri_complete,
                    user_code=runtime.user_code,
                    driver="qwen_oauth_proxy",
                    driver_state=runtime,
                    execution_mode="protocol_proxy",
                    trust_engine=context.trust_engine,
                    trust_path=context.trust_path,
                )

            runtime = self._manager._qwen_coding_plan_flow.start_session(  # noqa: SLF001
                session_id=context.session_id,
                provider_id=provider.provider_id,
            )
            return self._manager._new_session(  # noqa: SLF001
                session_id=context.session_id,
                engine="qwen",
                method=plan.method,
                auth_method=plan.auth_method,
                transport=plan.transport,
                provider_id=provider.provider_id,
                provider_name=provider.display_name,
                created_at=context.now,
                updated_at=context.now,
                expires_at=context.expires_at,
                status="starting",
                input_kind="api_key",
                output_path=context.output_path,
                process=None,
                driver="qwen_coding_plan_proxy",
                driver_state=runtime,
                execution_mode="protocol_proxy",
                trust_engine=context.trust_engine,
                trust_path=context.trust_path,
            )

        if plan.command is None:
            raise RuntimeError("qwen CLI not found")
        runtime = self._manager._qwen_flow.start_session(  # noqa: SLF001
            session_id=context.session_id,
            command_path=plan.command,
            cwd=context.session_dir,
            env=context.env,
            output_path=context.output_path,
            expires_at=context.expires_at,
            provider_id=provider.provider_id,
        )
        initial_input_kind = None if provider.provider_id == "qwen-oauth" else None
        return self._manager._new_session(  # noqa: SLF001
            session_id=context.session_id,
            engine="qwen",
            method=plan.method,
            auth_method=plan.auth_method,
            transport=plan.transport,
            provider_id=provider.provider_id,
            provider_name=provider.display_name,
            created_at=context.now,
            updated_at=context.now,
            expires_at=context.expires_at,
            status="starting",
            input_kind=initial_input_kind,
            output_path=context.output_path,
            process=runtime.process,
            auth_url=runtime.auth_url,
            user_code=runtime.user_code,
            driver="qwen",
            driver_state=runtime,
            execution_mode="cli_delegate",
            trust_engine=context.trust_engine,
            trust_path=context.trust_path,
        )

    def cleanup_start_error(self, *, context: StartRuntimeContext) -> None:
        _ = context

    def handle_input(self, session: Any, kind: str, value: str) -> None:
        runtime = session.driver_state
        if session.driver == "qwen_oauth_proxy":
            if kind != "text":
                raise ValueError("Qwen OAuth proxy only accepts text input")
            if runtime is None or not isinstance(runtime, QwenOAuthSession):
                raise ValueError("Qwen OAuth session driver is missing")
            behavior = self._session_behavior(
                transport=session.transport,
                provider_id=session.provider_id,
            )
            if not behavior.input_required and runtime.polling_started:
                session.status = "waiting_user"
                session.error = None
                session.updated_at = _utc_now()
                return
            self._manager._qwen_oauth_proxy_flow.submit_input(  # noqa: SLF001
                runtime,
                value,
                now=_utc_now(),
            )
            session.status = "code_submitted_waiting_result"
            session.error = None
            session.updated_at = _utc_now()
            return

        if session.driver == "qwen_coding_plan_proxy":
            if kind != "api_key":
                raise ValueError("Qwen Coding Plan proxy only accepts api_key input")
            if runtime is None or not isinstance(runtime, CodingPlanSession):
                raise ValueError("Qwen Coding Plan session driver is missing")
            try:
                self._manager._qwen_coding_plan_flow.complete_api_key(runtime, value)  # noqa: SLF001
                session.status = "succeeded"
                session.error = None
            except (OSError, RuntimeError, ValueError) as exc:
                session.status = "failed"
                session.error = str(exc)
            self._manager._finalize_active_session(session)  # noqa: SLF001
            return

        if session.driver != "qwen" or runtime is None or not isinstance(runtime, QwenAuthCliSession):
            raise ValueError("Input is only supported for active qwen auth sessions")
        if runtime.provider_id == "qwen-oauth":
            raise ValueError("Qwen OAuth delegated auth does not accept UI input")
        if kind != "api_key":
            raise ValueError("Qwen Coding Plan delegated auth only accepts api_key input")
        self._manager._qwen_flow.submit_api_key(runtime, value)  # noqa: SLF001

    def submit_legacy_input(self, session: Any, value: str) -> bool:
        runtime = session.driver_state
        if session.driver == "qwen_oauth_proxy" and isinstance(runtime, QwenOAuthSession):
            self.handle_input(session, "text", value)
            return True
        if (
            session.driver in {"qwen_coding_plan_proxy", "qwen"}
            and session.provider_id in {"coding-plan-china", "coding-plan-global"}
        ):
            self.handle_input(session, "api_key", value)
            return True
        return False

    def refresh_session_locked(self, session: Any) -> bool:
        runtime = session.driver_state
        if session.driver == "qwen":
            if runtime is None or not isinstance(runtime, QwenAuthCliSession):
                session.status = "failed"
                session.error = "Qwen auth session driver is missing"
                self._manager._finalize_active_session(session)  # noqa: SLF001
                return True
            self._manager._qwen_flow.refresh(runtime)  # noqa: SLF001
            session.updated_at = runtime.updated_at
            session.status = runtime.status
            session.auth_url = runtime.auth_url
            session.user_code = runtime.user_code
            session.error = runtime.error
            session.exit_code = runtime.exit_code
            if runtime.provider_id == "qwen-oauth":
                session.input_kind = None
            elif runtime.api_key_prompt_visible or runtime.api_key_submitted:
                session.input_kind = "api_key"
            else:
                session.input_kind = None
            if runtime.status in _TERMINAL_STATUSES:
                self._manager._finalize_active_session(session)  # noqa: SLF001
            return True

        now = _utc_now()
        session.updated_at = now
        if session.status in _TERMINAL_STATUSES:
            return True
        if now > session.expires_at:
            session.status = "expired"
            session.error = "Auth session expired"
            self._manager._finalize_active_session(session)  # noqa: SLF001
            return True

        if session.driver == "qwen_oauth_proxy":
            if runtime is None or not isinstance(runtime, QwenOAuthSession):
                session.status = "failed"
                session.error = "Qwen OAuth proxy session driver is missing"
                self._manager._finalize_active_session(session)  # noqa: SLF001
                return True
            behavior = self._session_behavior(
                transport=session.transport,
                provider_id=session.provider_id,
            )
            session.auth_url = runtime.verification_uri_complete
            session.user_code = runtime.user_code
            if runtime.polling_started:
                try:
                    completed = self._manager._qwen_oauth_proxy_flow.poll_once(  # noqa: SLF001
                        runtime,
                        now=now,
                    )
                    if completed:
                        session.status = "succeeded"
                        session.error = None
                        self._manager._finalize_active_session(session)  # noqa: SLF001
                    else:
                        session.status = (
                            "waiting_user"
                            if not behavior.input_required
                            else "code_submitted_waiting_result"
                        )
                except (OSError, RuntimeError, ValueError) as exc:
                    session.status = "failed"
                    session.error = str(exc)
                    self._manager._finalize_active_session(session)  # noqa: SLF001
            elif session.status == "starting":
                session.status = "waiting_user"
            session.input_kind = "text" if behavior.input_required else None
            return True

        if session.driver == "qwen_coding_plan_proxy":
            if runtime is None or not isinstance(runtime, CodingPlanSession):
                session.status = "failed"
                session.error = "Qwen Coding Plan proxy session driver is missing"
                self._manager._finalize_active_session(session)  # noqa: SLF001
                return True
            if session.status == "starting":
                session.status = "waiting_user"
            session.input_kind = "api_key"
            return True

        return False

    def terminate_session(self, session: Any) -> bool:
        runtime = session.driver_state
        if session.driver == "qwen" and runtime is not None and isinstance(runtime, QwenAuthCliSession):
            self._manager._qwen_flow.cancel(runtime)  # noqa: SLF001
            return True
        return False
