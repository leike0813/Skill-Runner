from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from server.engines.codebuddy.auth.provider_registry import require_provider
from server.runtime.auth.session_lifecycle import AuthStartPlan, StartRuntimeContext

from .sdk_auth_flow import CodeBuddySdkAuthSession


_TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "expired"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CodeBuddyAuthRuntimeHandler:
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
        provider = require_provider(provider_id)
        if transport != "oauth_proxy":
            raise ValueError("CodeBuddy auth only supports oauth_proxy")
        effective_method = auth_method or "auth_code_or_url"
        if effective_method != "auth_code_or_url":
            raise ValueError("CodeBuddy auth only supports auth_code_or_url")
        if not driver_registry.supports(
            transport=transport,
            engine="codebuddy",
            auth_method=effective_method,
            provider_id=provider.provider_id,
        ):
            raise ValueError("Unsupported CodeBuddy auth combination")
        command = resolve_engine_command("codebuddy")
        if command is None:
            raise RuntimeError("codebuddy CLI not found")
        return AuthStartPlan(
            engine="codebuddy",
            method=method,
            auth_method=effective_method,
            transport=transport,
            provider_id=provider.provider_id,
            provider=provider,
            registry_provider_id=provider.provider_id,
            command=command,
            requires_command=True,
        )

    def start_session_locked(
        self,
        *,
        plan: AuthStartPlan,
        callback_base_url: str | None,
        context: StartRuntimeContext,
    ) -> Any:
        _ = callback_base_url
        assert plan.provider is not None
        assert plan.command is not None
        runtime = self._manager._codebuddy_sdk_auth_flow.start(  # noqa: SLF001
            provider_id=plan.provider.provider_id,
            codebuddy_path=plan.command,
            timeout=max(1.0, (context.expires_at - context.now).total_seconds()),
        )
        return self._manager._new_session(  # noqa: SLF001
            session_id=context.session_id,
            engine="codebuddy",
            method=plan.method,
            auth_method=plan.auth_method,
            transport=plan.transport,
            provider_id=plan.provider.provider_id,
            provider_name=plan.provider.display_name,
            created_at=context.now,
            updated_at=context.now,
            expires_at=context.expires_at,
            status="starting",
            input_kind=None,
            output_path=None,
            process=runtime.process,
            auth_url=runtime.auth_url,
            driver="codebuddy_sdk_oauth_proxy",
            driver_state=runtime,
            execution_mode="protocol_proxy",
            trust_engine=context.trust_engine,
            trust_path=context.trust_path,
        )

    def cleanup_start_error(self, *, context: StartRuntimeContext) -> None:
        _ = context

    def handle_input(self, session: Any, kind: str, value: str) -> None:
        _ = session, kind, value
        raise ValueError("CodeBuddy authentication does not accept manual input")

    def submit_legacy_input(self, session: Any, value: str) -> bool:
        _ = session, value
        return False

    def refresh_session_locked(self, session: Any) -> bool:
        if session.driver != "codebuddy_sdk_oauth_proxy":
            return False
        runtime = session.driver_state
        if not isinstance(runtime, CodeBuddySdkAuthSession):
            session.status = "failed"
            session.error = "CodeBuddy auth worker state is missing"
            self._manager._finalize_active_session(session)  # noqa: SLF001
            return True
        now = _utc_now()
        session.updated_at = now
        if session.status in _TERMINAL_STATUSES:
            return True
        if now > session.expires_at:
            self._manager._codebuddy_sdk_auth_flow.cancel(runtime)  # noqa: SLF001
            session.status = "expired"
            session.error = "Auth session expired"
            self._manager._finalize_active_session(session)  # noqa: SLF001
            return True
        try:
            state = self._manager._codebuddy_sdk_auth_flow.poll(runtime)  # noqa: SLF001
        except (OSError, RuntimeError, ValueError) as exc:
            session.status = "failed"
            session.error = str(exc)
            session.exit_code = runtime.process.poll()
            self._manager._finalize_active_session(session)  # noqa: SLF001
            return True
        if state == "succeeded":
            session.status = "succeeded"
            session.error = None
            session.exit_code = runtime.process.poll()
            self._manager._finalize_active_session(session)  # noqa: SLF001
        else:
            session.status = "waiting_user"
            session.auth_url = runtime.auth_url
        return True

    def terminate_session(self, session: Any) -> bool:
        runtime = session.driver_state
        if session.driver != "codebuddy_sdk_oauth_proxy" or not isinstance(
            runtime, CodeBuddySdkAuthSession
        ):
            return False
        self._manager._codebuddy_sdk_auth_flow.cancel(runtime)  # noqa: SLF001
        return True

    def on_session_finalizing(self, session: Any) -> None:
        runtime = session.driver_state
        if isinstance(runtime, CodeBuddySdkAuthSession) and not runtime.cleaned:
            self._manager._codebuddy_sdk_auth_flow.cancel(runtime)  # noqa: SLF001

    def complete_callback(self, **kwargs: Any) -> bool:
        _ = kwargs
        return False
