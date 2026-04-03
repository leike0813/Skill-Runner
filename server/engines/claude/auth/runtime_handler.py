from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ....runtime.auth.session_lifecycle import AuthStartPlan, StartRuntimeContext
from .cli_delegate import ClaudeAuthCliSession
from .oauth_proxy import ClaudeOAuthProxySession

_DEFAULT_TRANSPORT = "oauth_proxy"
_AUTH_METHOD_CALLBACK = "callback"
_AUTH_METHOD_AUTH_CODE_OR_URL = "auth_code_or_url"
_TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "expired"}
_CLAUDE_MANUAL_REDIRECT_URI = "https://platform.claude.com/oauth/code/callback"
_CLAUDE_LOCAL_REDIRECT_URI = "http://127.0.0.1:51123/callback"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ClaudeAuthRuntimeHandler:
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
        if provider_id is not None:
            raise ValueError("provider_id is not supported for claude auth sessions")
        if transport == _DEFAULT_TRANSPORT:
            if auth_method is None:
                effective_auth_method = _AUTH_METHOD_CALLBACK
            elif auth_method in {_AUTH_METHOD_CALLBACK, _AUTH_METHOD_AUTH_CODE_OR_URL}:
                effective_auth_method = auth_method
            else:
                raise ValueError("Unsupported auth_method for claude oauth_proxy")
        elif transport == "cli_delegate":
            if auth_method is None:
                effective_auth_method = _AUTH_METHOD_AUTH_CODE_OR_URL
            elif auth_method == _AUTH_METHOD_AUTH_CODE_OR_URL:
                effective_auth_method = auth_method
            else:
                raise ValueError("Unsupported auth_method for claude cli_delegate")
        else:
            raise ValueError("Unsupported transport combination: claude only supports oauth_proxy|cli_delegate")
        if not driver_registry.supports(
            transport=transport,
            engine="claude",
            auth_method=effective_auth_method,
            provider_id=None,
        ):
            raise ValueError(
                "Unsupported auth combination: "
                f"transport={transport}, engine=claude, auth_method={effective_auth_method}, provider_id=-"
            )
        requires_command = transport != _DEFAULT_TRANSPORT
        command = resolve_engine_command("claude") if requires_command else None
        if requires_command and command is None:
            raise RuntimeError("claude CLI not found")
        return AuthStartPlan(
            engine="claude",
            method=method,
            auth_method=effective_auth_method,
            transport=transport,
            provider_id=None,
            provider=None,
            registry_provider_id=None,
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
        if plan.transport == _DEFAULT_TRANSPORT:
            listener_started = False
            callback_url = _CLAUDE_MANUAL_REDIRECT_URI
            if plan.auth_method == _AUTH_METHOD_CALLBACK:
                listener_started, endpoint = self._manager.start_callback_listener(
                    channel="claude",
                    callback_handler=lambda *, state, code=None, error=None: self._manager.complete_callback(
                        channel="claude",
                        state=state,
                        code=code,
                        error=error,
                    ),
                )
                if not listener_started:
                    raise ValueError("Claude callback mode requires local callback listener on localhost:51123")
                callback_url = endpoint.strip() if endpoint else _CLAUDE_LOCAL_REDIRECT_URI
                cleanup_state = context.cleanup_state if context.cleanup_state is not None else {}
                context.cleanup_state = cleanup_state
                cleanup_state["claude_listener_started"] = True
            runtime = self._manager._claude_oauth_proxy_flow.start_session(  # noqa: SLF001
                session_id=context.session_id,
                callback_url=callback_url,
                now=context.now,
            )
            self._manager.register_callback_state(  # noqa: SLF001
                channel="claude",
                session_id=context.session_id,
                state=runtime.state,
            )
            return self._manager._new_session(  # noqa: SLF001
                session_id=context.session_id,
                engine="claude",
                method=plan.method,
                auth_method=plan.auth_method,
                transport=plan.transport,
                provider_id=None,
                provider_name=None,
                created_at=context.now,
                updated_at=context.now,
                expires_at=context.expires_at,
                status="starting",
                input_kind="text",
                output_path=context.output_path,
                process=None,
                auth_url=runtime.auth_url,
                driver="claude_oauth_proxy",
                driver_state=runtime,
                execution_mode="protocol_proxy",
                trust_engine=context.trust_engine,
                trust_path=context.trust_path,
                audit={
                    "manual_fallback_used": False,
                    "auto_callback_success": False,
                    "local_callback_listener_started": listener_started,
                    "auto_callback_listener_started": listener_started,
                },
            )
        if plan.command is None:
            raise RuntimeError("claude CLI not found")
        runtime = self._manager._claude_flow.start_session(  # noqa: SLF001
            session_id=context.session_id,
            command_path=plan.command,
            cwd=context.session_dir,
            env=context.env,
            output_path=context.output_path,
            expires_at=context.expires_at,
        )
        return self._manager._new_session(  # noqa: SLF001
            session_id=context.session_id,
            engine="claude",
            method=plan.method,
            auth_method=plan.auth_method,
            transport=plan.transport,
            provider_id=None,
            provider_name=None,
            created_at=context.now,
            updated_at=context.now,
            expires_at=context.expires_at,
            status="starting",
            input_kind=None,
            output_path=context.output_path,
            process=runtime.process,
            auth_url=None,
            driver="claude",
            driver_state=runtime,
            execution_mode="cli_delegate",
            trust_engine=context.trust_engine,
            trust_path=context.trust_path,
        )

    def cleanup_start_error(self, *, context: StartRuntimeContext) -> None:
        if context.cleanup_state and context.cleanup_state.get("claude_listener_started"):
            self._manager.stop_callback_listener(channel="claude")  # noqa: SLF001

    def handle_input(self, session: Any, kind: str, value: str) -> None:
        if kind not in {"code", "text"}:
            raise ValueError("Claude auth only accepts code/text input")
        runtime = session.driver_state
        if isinstance(runtime, ClaudeOAuthProxySession):
            self._manager._mark_manual_fallback(session)  # noqa: SLF001
            session.status = "code_submitted_waiting_result"
            session.updated_at = _utc_now()
            try:
                flow_result = self._manager._claude_oauth_proxy_flow.submit_input(runtime, value)  # noqa: SLF001
                session.status = "succeeded"
                session.error = None
                audit = self._manager._ensure_audit_dict(session)  # noqa: SLF001
                audit["callback_mode"] = "manual"
                audit.update(flow_result)
                self._manager._finalize_active_session(session)  # noqa: SLF001
            except (OSError, RuntimeError, ValueError) as exc:
                session.status = "failed"
                session.error = str(exc)
                self._manager._finalize_active_session(session)  # noqa: SLF001
            return
        raise ValueError("Claude cli_delegate session does not accept manual input")

    def submit_legacy_input(self, session: Any, value: str) -> bool:
        _ = session
        _ = value
        return False

    def refresh_session_locked(self, session: Any) -> bool:
        runtime = session.driver_state
        if session.driver == "claude":
            if runtime is None or not isinstance(runtime, ClaudeAuthCliSession):
                session.status = "failed"
                session.error = "Claude auth session driver is missing"
                self._manager._finalize_active_session(session)  # noqa: SLF001
                return True
            self._manager._claude_flow.refresh(runtime)  # noqa: SLF001
            session.updated_at = runtime.updated_at
            session.status = runtime.status
            session.auth_url = runtime.auth_url
            session.user_code = None
            session.error = runtime.error
            session.exit_code = runtime.exit_code
            if runtime.status in _TERMINAL_STATUSES:
                self._manager._finalize_active_session(session)  # noqa: SLF001
            return True
        if session.driver == "claude_oauth_proxy":
            if runtime is None or not isinstance(runtime, ClaudeOAuthProxySession):
                session.status = "failed"
                session.error = "Claude OAuth proxy session driver is missing"
                self._manager._finalize_active_session(session)  # noqa: SLF001
                return True
            now = _utc_now()
            session.updated_at = now
            runtime.updated_at = now
            if session.status in _TERMINAL_STATUSES:
                return True
            if now > session.expires_at:
                session.status = "expired"
                session.error = "Auth session expired"
                self._manager._finalize_active_session(session)  # noqa: SLF001
                return True
            if session.status == "starting":
                session.status = "waiting_user"
            return True
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
        if channel != "claude" or session.engine != "claude":
            return False
        runtime = session.driver_state
        if runtime is None or not isinstance(runtime, ClaudeOAuthProxySession):
            session.status = "failed"
            session.error = "OAuth callback session does not support Claude callback"
            self._manager._finalize_active_session(session)  # noqa: SLF001
            return True
        if error and error.strip():
            session.status = "failed"
            session.error = f"OAuth callback error: {error.strip()}"
            self._manager._finalize_active_session(session)  # noqa: SLF001
            return True
        normalized_code = (code or "").strip()
        if not normalized_code:
            session.status = "failed"
            session.error = "OAuth callback code is missing"
            self._manager._finalize_active_session(session)  # noqa: SLF001
            return True
        try:
            flow_result = self._manager._claude_oauth_proxy_flow.complete_with_code(  # noqa: SLF001
                runtime=runtime,
                code=normalized_code,
                state=state,
            )
            session.status = "succeeded"
            session.error = None
            self._manager._mark_auto_callback_success(session)  # noqa: SLF001
            audit = self._manager._ensure_audit_dict(session)  # noqa: SLF001
            audit["callback_mode"] = "auto"
            audit.update(flow_result)
        except (OSError, RuntimeError, ValueError) as exc:
            session.status = "failed"
            session.error = f"OAuth callback token exchange failed: {exc}"
        self._manager._finalize_active_session(session)  # noqa: SLF001
        return True

    def terminate_session(self, session: Any) -> bool:
        runtime = session.driver_state
        if session.driver == "claude" and runtime is not None and isinstance(runtime, ClaudeAuthCliSession):
            self._manager._claude_flow.cancel(runtime)  # noqa: SLF001
            return True
        return False

    def on_session_finalizing(self, session: Any) -> None:
        runtime = session.driver_state
        if isinstance(runtime, ClaudeOAuthProxySession):
            self._manager.unregister_callback_state(channel="claude", state=runtime.state)  # noqa: SLF001
        if session.transport == _DEFAULT_TRANSPORT and session.driver == "claude_oauth_proxy":
            self._manager.stop_callback_listener(channel="claude")  # noqa: SLF001
