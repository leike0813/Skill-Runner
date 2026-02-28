from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ....runtime.auth.session_lifecycle import AuthStartPlan, StartRuntimeContext
from .cli_delegate import GeminiAuthCliSession
from .oauth_proxy import GeminiOAuthProxySession

_DEFAULT_TRANSPORT = "oauth_proxy"
_AUTH_METHOD_CALLBACK = "callback"
_AUTH_METHOD_AUTH_CODE_OR_URL = "auth_code_or_url"
_TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "expired"}
_GEMINI_MANUAL_REDIRECT_URI = "https://codeassist.google.com/authcode"
_GEMINI_LOCAL_REDIRECT_URI = "http://localhost:51122/oauth2callback"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GeminiAuthRuntimeHandler:
    def __init__(self, manager: Any) -> None:
        self._manager = manager

    def requires_parent_trust_bootstrap(self) -> bool:
        return True

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
            raise ValueError("provider_id is not supported for gemini auth sessions")
        if transport == _DEFAULT_TRANSPORT:
            if auth_method is None:
                effective_auth_method = _AUTH_METHOD_CALLBACK
            elif auth_method in {_AUTH_METHOD_CALLBACK, _AUTH_METHOD_AUTH_CODE_OR_URL}:
                effective_auth_method = auth_method
            else:
                raise ValueError("Unsupported auth_method for gemini oauth_proxy: use callback or auth_code_or_url")
        elif transport == "cli_delegate":
            if auth_method is None:
                effective_auth_method = _AUTH_METHOD_AUTH_CODE_OR_URL
            elif auth_method == _AUTH_METHOD_AUTH_CODE_OR_URL:
                effective_auth_method = auth_method
            else:
                raise ValueError("Unsupported auth_method for gemini cli_delegate: only auth_code_or_url is allowed")
        else:
            raise ValueError("Unsupported transport combination: gemini only supports oauth_proxy|cli_delegate")

        if not driver_registry.supports(
            transport=transport,
            engine="gemini",
            auth_method=effective_auth_method,
            provider_id=None,
        ):
            raise ValueError(
                "Unsupported auth combination: "
                f"transport={transport}, engine=gemini, auth_method={effective_auth_method}, provider_id=-"
            )
        requires_command = transport != _DEFAULT_TRANSPORT
        command = resolve_engine_command("gemini") if requires_command else None
        if requires_command and command is None:
            raise RuntimeError("gemini CLI not found")
        return AuthStartPlan(
            engine="gemini",
            method="auth",
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
        if plan.transport == _DEFAULT_TRANSPORT:
            if plan.auth_method == _AUTH_METHOD_CALLBACK:
                started, endpoint = self._manager.start_callback_listener(
                    channel="gemini",
                    callback_handler=lambda *, state, code=None, error=None: self._manager.complete_callback(
                        channel="gemini",
                        state=state,
                        code=code,
                        error=error,
                    ),
                )
                endpoint = endpoint if started else None
                listener_started = bool(endpoint)
                if not listener_started:
                    raise ValueError("Gemini callback mode requires local callback listener on localhost:51122")
                cleanup_state = context.cleanup_state if context.cleanup_state is not None else {}
                context.cleanup_state = cleanup_state
                cleanup_state["gemini_listener_started"] = True
                _ = callback_base_url
                callback_url = endpoint.strip() if endpoint else _GEMINI_LOCAL_REDIRECT_URI
                input_kind = "text"
            else:
                callback_url = _GEMINI_MANUAL_REDIRECT_URI
                input_kind = "text"
                listener_started = False
            runtime = self._manager._gemini_oauth_proxy_flow.start_session(  # noqa: SLF001
                session_id=context.session_id,
                callback_url=callback_url,
                now=context.now,
            )
            self._manager.register_callback_state(  # noqa: SLF001
                channel="gemini",
                session_id=context.session_id,
                state=runtime.state,
            )
            return self._manager._new_session(  # noqa: SLF001
                session_id=context.session_id,
                engine="gemini",
                method=plan.method,
                auth_method=plan.auth_method,
                transport=plan.transport,
                provider_id=None,
                provider_name=None,
                created_at=context.now,
                updated_at=context.now,
                expires_at=context.expires_at,
                status="starting",
                input_kind=input_kind,
                output_path=context.output_path,
                process=None,
                auth_url=runtime.auth_url,
                driver="gemini_oauth_proxy",
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
        self._manager._prepare_gemini_auth_workspace(context.session_dir)  # noqa: SLF001
        if plan.command is None:
            raise RuntimeError("gemini CLI not found")
        runtime = self._manager._gemini_flow.start_session(  # noqa: SLF001
            session_id=context.session_id,
            command_path=plan.command,
            cwd=context.session_dir,
            env=context.env,
            output_path=context.output_path,
            expires_at=context.expires_at,
        )
        return self._manager._new_session(  # noqa: SLF001
            session_id=context.session_id,
            engine="gemini",
            method=plan.method,
            auth_method=plan.auth_method,
            transport=plan.transport,
            provider_id=None,
            provider_name=None,
            created_at=context.now,
            updated_at=context.now,
            expires_at=context.expires_at,
            status="starting",
            input_kind="code",
            output_path=context.output_path,
            process=runtime.process,
            driver="gemini",
            driver_state=runtime,
            trust_engine=context.trust_engine,
            trust_path=context.trust_path,
        )

    def cleanup_start_error(self, *, context: StartRuntimeContext) -> None:
        if context.cleanup_state and context.cleanup_state.get("gemini_listener_started"):
            self._manager.stop_callback_listener(channel="gemini")  # noqa: SLF001

    def handle_input(self, session: Any, kind: str, value: str) -> None:
        if kind not in {"code", "text"}:
            raise ValueError("Gemini auth only accepts code/text input")
        runtime = session.driver_state
        if isinstance(runtime, GeminiOAuthProxySession):
            self._manager._mark_manual_fallback(session)  # noqa: SLF001
            session.status = "code_submitted_waiting_result"
            session.updated_at = _utc_now()
            try:
                flow_result = self._manager._gemini_oauth_proxy_flow.submit_input(runtime, value)  # noqa: SLF001
                session.status = "succeeded"
                session.error = None
                session.auth_ready = self._manager._collect_auth_ready("gemini")  # noqa: SLF001
                audit = self._manager._ensure_audit_dict(session)  # noqa: SLF001
                audit["callback_mode"] = "manual"
                audit.update(flow_result)
                self._manager._finalize_active_session(session)  # noqa: SLF001
            except Exception as exc:
                session.status = "failed"
                session.error = str(exc)
                session.auth_ready = self._manager._collect_auth_ready("gemini")  # noqa: SLF001
                self._manager._finalize_active_session(session)  # noqa: SLF001
            return
        if runtime is None or not isinstance(runtime, GeminiAuthCliSession):
            raise ValueError("Input is only supported for active delegated auth sessions")
        self._manager._gemini_flow.submit_code(runtime, value)  # noqa: SLF001

    def submit_legacy_input(self, session: Any, value: str) -> bool:
        return False

    def refresh_session_locked(self, session: Any) -> bool:
        runtime = session.driver_state
        if session.driver == "gemini":
            if runtime is None or not isinstance(runtime, GeminiAuthCliSession):
                session.status = "failed"
                session.error = "Gemini auth session driver is missing"
                session.auth_ready = False
                if self._manager._active_session_id == session.session_id:  # noqa: SLF001
                    self._manager._active_session_id = None  # noqa: SLF001
                self._manager.interaction_gate.release("auth_flow", session.session_id)
                return True
            self._manager._gemini_flow.refresh(runtime)  # noqa: SLF001
            session.updated_at = runtime.updated_at
            session.status = runtime.status
            session.auth_url = runtime.auth_url
            session.user_code = None
            session.error = runtime.error
            session.exit_code = runtime.exit_code
            session.auth_ready = runtime.status == "succeeded"
            if runtime.status in _TERMINAL_STATUSES:
                self._manager._finalize_active_session(session)  # noqa: SLF001
            return True
        if session.driver == "gemini_oauth_proxy":
            if runtime is None or not isinstance(runtime, GeminiOAuthProxySession):
                session.status = "failed"
                session.error = "Gemini OAuth proxy session driver is missing"
                session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
                self._manager._finalize_active_session(session)  # noqa: SLF001
                return True
            now = _utc_now()
            session.updated_at = now
            runtime.updated_at = now
            if session.status in _TERMINAL_STATUSES:
                session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
                return True
            if now > session.expires_at:
                session.status = "expired"
                session.error = "Auth session expired"
                session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
                self._manager._finalize_active_session(session)  # noqa: SLF001
                return True
            if session.status == "starting":
                session.status = "waiting_user"
            session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
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
        if channel != "gemini" or session.engine != "gemini":
            return False
        runtime = session.driver_state
        if runtime is None or not isinstance(runtime, GeminiOAuthProxySession):
            session.status = "failed"
            session.error = "OAuth callback session does not support Gemini callback"
            session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
            self._manager._finalize_active_session(session)  # noqa: SLF001
            return True
        if error and error.strip():
            session.status = "failed"
            session.error = f"OAuth callback error: {error.strip()}"
            session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
            self._manager._finalize_active_session(session)  # noqa: SLF001
            return True
        normalized_code = (code or "").strip()
        if not normalized_code:
            session.status = "failed"
            session.error = "OAuth callback code is missing"
            session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
            self._manager._finalize_active_session(session)  # noqa: SLF001
            return True
        try:
            flow_result = self._manager._gemini_oauth_proxy_flow.complete_with_code(  # noqa: SLF001
                runtime=runtime,
                code=normalized_code,
                state=state,
            )
            session.status = "succeeded"
            session.error = None
            session.auth_ready = self._manager._collect_auth_ready("gemini")  # noqa: SLF001
            self._manager._mark_auto_callback_success(session)  # noqa: SLF001
            audit = self._manager._ensure_audit_dict(session)  # noqa: SLF001
            audit["callback_mode"] = "auto"
            audit.update(flow_result)
        except Exception as exc:
            session.status = "failed"
            session.error = f"OAuth callback token exchange failed: {exc}"
            session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
        self._manager._finalize_active_session(session)  # noqa: SLF001
        return True

    def terminate_session(self, session: Any) -> bool:
        runtime = session.driver_state
        if session.driver == "gemini" and runtime is not None and isinstance(runtime, GeminiAuthCliSession):
            self._manager._gemini_flow.cancel(runtime)  # noqa: SLF001
            return True
        return False

    def on_session_finalizing(self, session: Any) -> None:
        runtime = session.driver_state
        if isinstance(runtime, GeminiOAuthProxySession):
            self._manager.unregister_callback_state(channel="gemini", state=runtime.state)  # noqa: SLF001
        if session.transport == _DEFAULT_TRANSPORT and session.driver == "gemini_oauth_proxy":
            self._manager.stop_callback_listener(channel="gemini")  # noqa: SLF001
