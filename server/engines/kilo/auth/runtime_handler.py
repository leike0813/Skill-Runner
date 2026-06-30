from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from server.engines.opencode.auth.provider_registry import (
    opencode_auth_provider_registry,
)
from server.engines.opencode.auth.runtime_handler import OpencodeAuthRuntimeHandler
from server.runtime.auth.session_lifecycle import AuthStartPlan, StartRuntimeContext
from server.services.engine_management.engine_auth_strategy_service import (
    SessionBehaviorPolicy,
    engine_auth_strategy_service,
)
from server.services.engine_management.provider_aware_auth import get_engine_auth_provider

from .protocol.kilo_gateway_device_auth_flow import KiloGatewayDeviceAuthSession
from .provider_registry import kilo_auth_provider_registry

_DEFAULT_TRANSPORT = "oauth_proxy"
_AUTH_METHOD_AUTH_CODE_OR_URL = "auth_code_or_url"
_TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "expired"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class KiloAuthRuntimeHandler:
    def __init__(self, manager: Any) -> None:
        self._manager = manager
        self._opencode_handler = OpencodeAuthRuntimeHandler(
            manager,
            auth_store_factory=manager._build_kilo_auth_store,  # noqa: SLF001
            openai_oauth_flow_attr="_kilo_opencode_openai_oauth_proxy_flow",
        )

    def requires_parent_trust_bootstrap(self) -> bool:
        return False

    def _session_behavior(
        self,
        *,
        transport: str,
        provider_id: str | None,
    ) -> SessionBehaviorPolicy:
        return engine_auth_strategy_service.runtime_session_behavior_for_transport(
            engine="kilo",
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
        provider = get_engine_auth_provider("kilo", provider_id)
        normalized_provider_id = provider.provider_id
        if normalized_provider_id == "kilo":
            if transport != _DEFAULT_TRANSPORT:
                raise ValueError("Kilo Gateway auth only supports oauth_proxy")
            if auth_method is None:
                effective_auth_method = _AUTH_METHOD_AUTH_CODE_OR_URL
            elif auth_method == _AUTH_METHOD_AUTH_CODE_OR_URL:
                effective_auth_method = auth_method
            else:
                raise ValueError("Unsupported auth_method for Kilo Gateway: use auth_code_or_url")
            if not driver_registry.supports(
                transport=transport,
                engine="kilo",
                auth_method=effective_auth_method,
                provider_id=normalized_provider_id,
            ):
                raise ValueError(
                    "Unsupported auth combination: "
                    f"transport={transport}, engine=kilo, auth_method={effective_auth_method}, "
                    f"provider_id={normalized_provider_id}"
                )
            return AuthStartPlan(
                engine="kilo",
                method=method,
                auth_method=effective_auth_method,
                transport=transport,
                provider_id=normalized_provider_id,
                provider=provider,
                registry_provider_id=normalized_provider_id,
                command=None,
                requires_command=False,
            )

        kilo_auth_provider_registry.get(normalized_provider_id)
        opencode_plan = self._opencode_handler.plan_start(
            method=method,
            auth_method=auth_method,
            transport=transport,
            provider_id=normalized_provider_id,
            driver_registry=driver_registry,
            resolve_engine_command=resolve_engine_command,
        )
        if not driver_registry.supports(
            transport=transport,
            engine="kilo",
            auth_method=opencode_plan.auth_method,
            provider_id=normalized_provider_id,
        ):
            raise ValueError(
                "Unsupported auth combination: "
                f"transport={transport}, engine=kilo, auth_method={opencode_plan.auth_method}, "
                f"provider_id={normalized_provider_id}"
            )
        return replace(
            opencode_plan,
            engine="kilo",
            provider_id=normalized_provider_id,
            provider=provider,
            registry_provider_id=normalized_provider_id,
        )

    def start_session_locked(
        self,
        *,
        plan: AuthStartPlan,
        callback_base_url: str | None,
        context: StartRuntimeContext,
    ) -> Any:
        provider = plan.provider
        assert provider is not None
        if provider.provider_id == "kilo":
            behavior = self._session_behavior(
                transport=plan.transport,
                provider_id=provider.provider_id,
            )
            runtime = self._manager._kilo_gateway_device_auth_flow.start_session(  # noqa: SLF001
                session_id=context.session_id,
                now=context.now,
            )
            if behavior.polling_start == "immediate":
                self._manager._kilo_gateway_device_auth_flow.start_polling(  # noqa: SLF001
                    runtime,
                    now=context.now,
                    poll_now=False,
                )
            return self._manager._new_session(  # noqa: SLF001
                session_id=context.session_id,
                engine="kilo",
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
                auth_url=runtime.verification_url,
                user_code=runtime.user_code,
                driver="kilo_gateway_oauth_proxy",
                driver_state=runtime,
                execution_mode="protocol_proxy",
                trust_engine=context.trust_engine,
                trust_path=context.trust_path,
            )

        opencode_provider = opencode_auth_provider_registry.get(provider.provider_id)
        opencode_plan = replace(
            plan,
            engine="opencode",
            provider=opencode_provider,
            provider_id=opencode_provider.provider_id,
            registry_provider_id=opencode_provider.provider_id,
        )
        session = self._opencode_handler.start_session_locked(
            plan=opencode_plan,
            callback_base_url=callback_base_url,
            context=context,
        )
        session.engine = "kilo"
        session.provider_id = provider.provider_id
        session.provider_name = provider.display_name
        return session

    def cleanup_start_error(self, *, context: StartRuntimeContext) -> None:
        self._opencode_handler.cleanup_start_error(context=context)

    def handle_input(self, session: Any, kind: str, value: str) -> None:
        if session.driver == "kilo_gateway_oauth_proxy":
            raise ValueError("Kilo Gateway device auth does not accept manual input")
        self._opencode_handler.handle_input(session, kind, value)
        session.engine = "kilo"

    def submit_legacy_input(self, session: Any, value: str) -> bool:
        if session.driver == "kilo_gateway_oauth_proxy":
            return False
        handled = self._opencode_handler.submit_legacy_input(session, value)
        session.engine = "kilo"
        return handled

    def refresh_session_locked(self, session: Any) -> bool:
        runtime = session.driver_state
        if session.driver == "kilo_gateway_oauth_proxy":
            if runtime is None or not isinstance(runtime, KiloGatewayDeviceAuthSession):
                session.status = "failed"
                session.error = "Kilo Gateway auth session driver is missing"
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
            behavior = self._session_behavior(
                transport=session.transport,
                provider_id=session.provider_id,
            )
            session.auth_url = runtime.verification_url
            session.user_code = runtime.user_code
            if runtime.polling_started:
                try:
                    completed = self._manager._kilo_gateway_device_auth_flow.poll_once(  # noqa: SLF001
                        runtime,
                        now=now,
                    )
                    if completed:
                        session.status = "succeeded"
                        session.error = None
                        self._manager._finalize_active_session(session)  # noqa: SLF001
                    else:
                        session.status = "waiting_user"
                except (OSError, RuntimeError, ValueError) as exc:
                    session.status = "failed"
                    session.error = str(exc)
                    self._manager._finalize_active_session(session)  # noqa: SLF001
            elif session.status == "starting":
                session.status = "waiting_user"
            session.input_kind = "text" if behavior.input_required else None
            return True

        handled = self._opencode_handler.refresh_session_locked(session)
        session.engine = "kilo"
        return handled

    def terminate_session(self, session: Any) -> bool:
        if session.driver == "kilo_gateway_oauth_proxy":
            return True
        terminate = getattr(self._opencode_handler, "terminate_session", None)
        if callable(terminate):
            return bool(terminate(session))
        return False

    def complete_callback(
        self,
        *,
        channel: str,
        session: Any,
        state: str,
        code: str | None,
        error: str | None,
    ) -> bool:
        if session.driver == "kilo_gateway_oauth_proxy":
            return False
        original_engine = session.engine
        session.engine = "opencode"
        try:
            return self._opencode_handler.complete_callback(
                channel=channel,
                session=session,
                state=state,
                code=code,
                error=error,
            )
        finally:
            session.engine = original_engine
