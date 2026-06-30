from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from server.runtime.auth.session_lifecycle import AuthStartPlan, StartRuntimeContext
from server.services.engine_management.provider_aware_auth import get_engine_auth_provider

from .drivers.cli_delegate_flow import QwenAuthCliSession
from .protocol.coding_plan_flow import CodingPlanSession

_DEFAULT_TRANSPORT = "oauth_proxy"
_AUTH_METHOD_API_KEY = "api_key"
_TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "expired"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class QwenAuthRuntimeHandler:
    def __init__(self, manager: Any) -> None:
        self._manager = manager

    def requires_parent_trust_bootstrap(self) -> bool:
        return False

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
        if auth_method is None:
            effective_auth_method = _AUTH_METHOD_API_KEY
        elif auth_method == _AUTH_METHOD_API_KEY:
            effective_auth_method = auth_method
        else:
            raise ValueError("Unsupported auth_method for Qwen API-key provider: use api_key")

        if transport != _DEFAULT_TRANSPORT:
            raise ValueError("Unsupported transport combination: qwen only supports oauth_proxy")
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

        _ = resolve_engine_command

        return AuthStartPlan(
            engine="qwen",
            method=method,
            auth_method=effective_auth_method,
            transport=transport,
            provider_id=normalized_provider_id,
            provider=provider,
            registry_provider_id=normalized_provider_id,
            command=None,
            requires_command=False,
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

        raise ValueError("Unsupported transport combination: qwen only supports oauth_proxy")

    def cleanup_start_error(self, *, context: StartRuntimeContext) -> None:
        _ = context

    def handle_input(self, session: Any, kind: str, value: str) -> None:
        runtime = session.driver_state
        if session.driver == "qwen_coding_plan_proxy":
            if kind != "api_key":
                raise ValueError("Qwen API-key proxy only accepts api_key input")
            if runtime is None or not isinstance(runtime, CodingPlanSession):
                raise ValueError("Qwen API-key session driver is missing")
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
        if kind != "api_key":
            raise ValueError("Qwen delegated auth only accepts api_key input")
        self._manager._qwen_flow.submit_api_key(runtime, value)  # noqa: SLF001

    def submit_legacy_input(self, session: Any, value: str) -> bool:
        if session.driver in {"qwen_coding_plan_proxy", "qwen"}:
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
            if runtime.api_key_prompt_visible or runtime.api_key_submitted:
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

        if session.driver == "qwen_coding_plan_proxy":
            if runtime is None or not isinstance(runtime, CodingPlanSession):
                session.status = "failed"
                session.error = "Qwen API-key session driver is missing"
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
