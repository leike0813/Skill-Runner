from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ....config import config
from ....runtime.auth.session_lifecycle import AuthStartPlan, StartRuntimeContext
from ....services.openai_device_proxy_flow import OpenAIDeviceProxySession
from .auth_store import OpencodeAuthStore
from .cli_delegate import OpencodeAuthCliSession
from .google_antigravity_oauth_proxy import OpencodeGoogleAntigravityOAuthProxySession
from .openai_oauth_proxy import OpencodeOpenAIOAuthProxySession
from .provider_registry import OpencodeAuthProvider, opencode_auth_provider_registry

_DEFAULT_TRANSPORT = "oauth_proxy"
_AUTH_METHOD_CALLBACK = "callback"
_AUTH_METHOD_AUTH_CODE_OR_URL = "auth_code_or_url"
_AUTH_METHOD_API_KEY = "api_key"
_TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "expired"}
_OPENAI_DEVICE_USER_AGENT_OPENCODE = "opencode/skill-runner"
_OPENAI_LOCAL_REDIRECT_URI = "http://localhost:1455/auth/callback"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_openai_callback_url(callback_base_url: str | None = None) -> str:
    configured = str(config.SYSTEM.ENGINE_AUTH_OAUTH_CALLBACK_BASE_URL or "").strip()
    if configured:
        if configured.endswith("/auth/callback"):
            return configured.rstrip("/")
        return f"{configured.rstrip('/')}/auth/callback"
    _ = callback_base_url
    return _OPENAI_LOCAL_REDIRECT_URI


class OpencodeAuthRuntimeHandler:
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
        if not provider_id:
            raise ValueError("provider_id is required for opencode auth sessions")
        provider = opencode_auth_provider_registry.get(provider_id)
        if provider.auth_mode == "api_key":
            if transport != _DEFAULT_TRANSPORT:
                raise ValueError(
                    "Unsupported transport combination: OpenCode API key providers require oauth_proxy transport"
                )
            if auth_method and auth_method != _AUTH_METHOD_API_KEY:
                raise ValueError("Unsupported auth_method for OpenCode API key provider: use api_key")
            effective_auth_method = _AUTH_METHOD_API_KEY
        elif transport == _DEFAULT_TRANSPORT and provider.provider_id not in {"openai", "google"}:
            raise ValueError(
                "Unsupported transport combination: opencode oauth_proxy only supports provider_id=openai|google"
            )
        elif provider.provider_id == "openai":
            if auth_method is None:
                effective_auth_method = _AUTH_METHOD_CALLBACK
            elif auth_method in {_AUTH_METHOD_CALLBACK, _AUTH_METHOD_AUTH_CODE_OR_URL}:
                effective_auth_method = auth_method
            else:
                raise ValueError("Unsupported auth_method for OpenCode OpenAI: use callback or auth_code_or_url")
        elif provider.provider_id == "google" and transport == _DEFAULT_TRANSPORT:
            if auth_method is None:
                effective_auth_method = _AUTH_METHOD_CALLBACK
            elif auth_method in {_AUTH_METHOD_CALLBACK, _AUTH_METHOD_AUTH_CODE_OR_URL}:
                effective_auth_method = auth_method
            else:
                raise ValueError(
                    "Unsupported auth_method for OpenCode Google oauth_proxy: use callback or auth_code_or_url"
                )
        else:
            if provider.provider_id == "google":
                if auth_method is None:
                    effective_auth_method = _AUTH_METHOD_AUTH_CODE_OR_URL
                elif auth_method == _AUTH_METHOD_AUTH_CODE_OR_URL:
                    effective_auth_method = auth_method
                else:
                    raise ValueError(
                        "Unsupported auth_method for OpenCode Google cli_delegate: only auth_code_or_url is allowed"
                    )
            else:
                if auth_method is None:
                    effective_auth_method = _AUTH_METHOD_CALLBACK
                elif auth_method in {_AUTH_METHOD_CALLBACK, _AUTH_METHOD_AUTH_CODE_OR_URL}:
                    effective_auth_method = auth_method
                else:
                    raise ValueError(
                        "Unsupported auth_method for OpenCode OAuth provider: use callback or auth_code_or_url"
                    )
        registry_provider_id = None if provider.auth_mode == "api_key" else provider.provider_id
        if not driver_registry.supports(
            transport=transport,
            engine="opencode",
            auth_method=effective_auth_method,
            provider_id=registry_provider_id,
        ):
            raise ValueError(
                "Unsupported auth combination: "
                f"transport={transport}, engine=opencode, auth_method={effective_auth_method}, "
                f"provider_id={registry_provider_id or '-'}"
            )
        requires_command = True
        if transport == _DEFAULT_TRANSPORT and provider.provider_id in {"openai", "google"}:
            requires_command = False
        if provider.auth_mode == "api_key":
            requires_command = False
        command = resolve_engine_command("opencode") if requires_command else None
        if requires_command and command is None:
            raise RuntimeError("opencode CLI not found")
        return AuthStartPlan(
            engine="opencode",
            method="auth",
            auth_method=effective_auth_method,
            transport=transport,
            provider_id=provider.provider_id,
            provider=provider,
            registry_provider_id=registry_provider_id,
            command=command,
            requires_command=requires_command,
        )

    def _auth_store(self) -> OpencodeAuthStore:
        return self._manager._build_opencode_auth_store()  # noqa: SLF001

    def start_session_locked(
        self,
        *,
        plan: AuthStartPlan,
        callback_base_url: str | None,
        context: StartRuntimeContext,
    ) -> Any:
        provider = plan.provider
        assert provider is not None
        if plan.transport == _DEFAULT_TRANSPORT and provider.provider_id in {"openai", "google"}:
            if provider.provider_id == "openai" and plan.auth_method == _AUTH_METHOD_CALLBACK:
                listener_started, _ = self._manager.start_callback_listener(
                    channel="openai",
                    callback_handler=lambda *, state, code=None, error=None: self._manager.complete_callback(
                        channel="openai",
                        state=state,
                        code=code,
                        error=error,
                    ),
                )
                if not listener_started:
                    raise ValueError("OpenCode OpenAI callback mode requires local callback listener on localhost:1455")
                cleanup_state = context.cleanup_state if context.cleanup_state is not None else {}
                context.cleanup_state = cleanup_state
                cleanup_state["openai_listener_started"] = True
                runtime = self._manager._opencode_openai_oauth_proxy_flow.start_session(  # noqa: SLF001
                    session_id=context.session_id,
                    callback_url=_resolve_openai_callback_url(callback_base_url),
                    now=context.now,
                )
                self._manager.register_callback_state(  # noqa: SLF001
                    channel="openai",
                    session_id=context.session_id,
                    state=runtime.state,
                )
                return self._manager._new_session(  # noqa: SLF001
                    session_id=context.session_id,
                    engine="opencode",
                    method=plan.method,
                    auth_method=plan.auth_method,
                    transport=plan.transport,
                    provider_id=provider.provider_id,
                    provider_name=provider.display_name,
                    created_at=context.now,
                    updated_at=context.now,
                    expires_at=context.expires_at,
                    status="starting",
                    input_kind="text",
                    output_path=context.output_path,
                    process=None,
                    auth_url=runtime.auth_url,
                    driver="opencode_openai_oauth_proxy",
                    driver_state=runtime,
                    execution_mode="protocol_proxy",
                    audit={
                        "manual_fallback_used": False,
                        "auto_callback_success": False,
                        "local_callback_listener_started": listener_started,
                        "auto_callback_listener_started": listener_started,
                    },
                    trust_engine=context.trust_engine,
                    trust_path=context.trust_path,
                )
            if provider.provider_id == "openai":
                try:
                    runtime = self._manager._openai_device_proxy_flow.start_session(  # noqa: SLF001
                        session_id=context.session_id,
                        now=context.now,
                        user_agent=_OPENAI_DEVICE_USER_AGENT_OPENCODE,
                    )
                except Exception as exc:
                    raise self._manager._build_openai_device_start_error(exc) from exc  # noqa: SLF001
                return self._manager._new_session(  # noqa: SLF001
                    session_id=context.session_id,
                    engine="opencode",
                    method=plan.method,
                    auth_method=plan.auth_method,
                    transport=plan.transport,
                    provider_id=provider.provider_id,
                    provider_name=provider.display_name,
                    created_at=context.now,
                    updated_at=context.now,
                    expires_at=context.expires_at,
                    status="starting",
                    input_kind=None,
                    output_path=context.output_path,
                    process=None,
                    auth_url=runtime.verification_url,
                    user_code=runtime.user_code,
                    driver="opencode_openai_device_oauth_proxy",
                    driver_state=runtime,
                    execution_mode="protocol_proxy",
                    audit={
                        "manual_fallback_used": False,
                        "auto_callback_success": False,
                        "local_callback_listener_started": False,
                    },
                    trust_engine=context.trust_engine,
                    trust_path=context.trust_path,
                )

            listener_started = False
            if plan.auth_method == _AUTH_METHOD_CALLBACK:
                listener_started, _ = self._manager.start_callback_listener(
                    channel="antigravity",
                    callback_handler=lambda *, state, code=None, error=None: self._manager.complete_callback(
                        channel="antigravity",
                        state=state,
                        code=code,
                        error=error,
                    ),
                )
                if not listener_started:
                    raise ValueError("OpenCode Google callback mode requires local callback listener on localhost:51121")
                cleanup_state = context.cleanup_state if context.cleanup_state is not None else {}
                context.cleanup_state = cleanup_state
                cleanup_state["antigravity_listener_started"] = True
            runtime = self._manager._opencode_google_antigravity_oauth_proxy_flow.start_session(  # noqa: SLF001
                session_id=context.session_id,
                auth_method=plan.auth_method,
                now=context.now,
            )
            self._manager.register_callback_state(  # noqa: SLF001
                channel="antigravity",
                session_id=context.session_id,
                state=runtime.state,
            )
            return self._manager._new_session(  # noqa: SLF001
                session_id=context.session_id,
                engine="opencode",
                method=plan.method,
                auth_method=plan.auth_method,
                transport=plan.transport,
                provider_id=provider.provider_id,
                provider_name=provider.display_name,
                created_at=context.now,
                updated_at=context.now,
                expires_at=context.expires_at,
                status="starting",
                input_kind="text",
                output_path=context.output_path,
                process=None,
                auth_url=runtime.auth_url,
                driver="opencode_google_antigravity_oauth_proxy",
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

        audit: dict[str, Any] = {}
        auth_store = self._auth_store()
        if provider.provider_id == "google":
            backup_info = auth_store.backup_antigravity_accounts(
                context.session_dir / "antigravity-accounts.pre_auth.backup.json"
            )
            try:
                cleanup = auth_store.clear_antigravity_accounts()
                audit["google_antigravity_cleanup"] = {
                    "executed": True,
                    "success": True,
                    **backup_info,
                    **cleanup,
                }
            except Exception as exc:
                rollback_success = False
                rollback_error: str | None = None
                try:
                    auth_store.restore_antigravity_accounts(
                        source_exists=bool(backup_info.get("source_exists")),
                        backup_path=(str(backup_info.get("backup_path")) if backup_info.get("backup_path") else None),
                    )
                    rollback_success = True
                except Exception as rollback_exc:
                    rollback_error = str(rollback_exc)
                session = self._manager._new_session(  # noqa: SLF001
                    session_id=context.session_id,
                    engine="opencode",
                    method=plan.method,
                    auth_method=plan.auth_method,
                    transport=plan.transport,
                    provider_id=provider.provider_id,
                    provider_name=provider.display_name,
                    created_at=context.now,
                    updated_at=context.now,
                    expires_at=context.expires_at,
                    status="failed",
                    input_kind="text",
                    output_path=context.output_path,
                    process=None,
                    driver="opencode",
                    audit={
                        "google_antigravity_cleanup": {
                            "executed": True,
                            "success": False,
                            "error": str(exc),
                            **backup_info,
                            "rollback_attempted": True,
                            "rollback_success": rollback_success,
                            "rollback_error": rollback_error,
                        }
                    },
                    error=f"Failed to clear Google AntiGravity accounts: {exc}",
                    auth_ready=self._manager._collect_auth_ready("opencode"),  # noqa: SLF001
                    execution_mode="cli_delegate",
                    trust_engine=context.trust_engine,
                    trust_path=context.trust_path,
                )
                session.log_root = context.session_dir
                return session

        if provider.auth_mode == "api_key":
            return self._manager._new_session(  # noqa: SLF001
                session_id=context.session_id,
                engine="opencode",
                method=plan.method,
                auth_method=plan.auth_method,
                transport=plan.transport,
                provider_id=provider.provider_id,
                provider_name=provider.display_name,
                created_at=context.now,
                updated_at=context.now,
                expires_at=context.expires_at,
                status="waiting_user",
                input_kind="api_key",
                output_path=None,
                process=None,
                driver="opencode",
                driver_state=None,
                execution_mode="protocol_proxy",
                audit=audit or None,
                trust_engine=context.trust_engine,
                trust_path=context.trust_path,
            )
        if plan.command is None:
            raise RuntimeError("opencode CLI not found")
        runtime = self._manager._opencode_flow.start_session(  # noqa: SLF001
            session_id=context.session_id,
            command_path=plan.command,
            cwd=context.session_dir,
            env=context.env,
            output_path=context.output_path,
            expires_at=context.expires_at,
            provider_id=provider.provider_id,
            provider_label=provider.menu_label,
            openai_auth_method=plan.auth_method,
        )
        input_kind: str | None = "text"
        if provider.provider_id == "openai" and plan.auth_method == _AUTH_METHOD_AUTH_CODE_OR_URL:
            input_kind = None
        return self._manager._new_session(  # noqa: SLF001
            session_id=context.session_id,
            engine="opencode",
            method=plan.method,
            auth_method=plan.auth_method,
            transport=plan.transport,
            provider_id=provider.provider_id,
            provider_name=provider.display_name,
            created_at=context.now,
            updated_at=context.now,
            expires_at=context.expires_at,
            status="starting",
            input_kind=input_kind,
            output_path=context.output_path,
            process=runtime.process,
            driver="opencode",
            driver_state=runtime,
            execution_mode="cli_delegate",
            audit=audit or None,
            trust_engine=context.trust_engine,
            trust_path=context.trust_path,
        )

    def cleanup_start_error(self, *, context: StartRuntimeContext) -> None:
        if context.cleanup_state and context.cleanup_state.get("openai_listener_started"):
            self._manager.stop_callback_listener(channel="openai")  # noqa: SLF001
        if context.cleanup_state and context.cleanup_state.get("antigravity_listener_started"):
            self._manager.stop_callback_listener(channel="antigravity")  # noqa: SLF001

    def handle_input(self, session: Any, kind: str, value: str) -> None:
        if session.input_kind == "api_key":
            if kind != "api_key":
                raise ValueError("OpenCode API key flow only accepts api_key input")
            if not session.provider_id:
                raise ValueError("OpenCode provider is missing")
            auth_store = self._auth_store()
            auth_store.upsert_api_key(session.provider_id, value)
            session.status = "succeeded"
            session.updated_at = _utc_now()
            session.auth_ready = self._manager._collect_auth_ready("opencode")  # noqa: SLF001
            session.error = None
            self._manager._finalize_active_session(session)  # noqa: SLF001
            return
        if kind not in {"code", "text"}:
            raise ValueError("OpenCode OAuth flow only accepts text/code input")
        runtime = session.driver_state
        if isinstance(runtime, OpencodeOpenAIOAuthProxySession):
            self._manager._mark_manual_fallback(session)  # noqa: SLF001
            session.status = "code_submitted_waiting_result"
            session.updated_at = _utc_now()
            try:
                self._manager._opencode_openai_oauth_proxy_flow.submit_input(runtime, value)  # noqa: SLF001
                session.status = "succeeded"
                session.error = None
                session.auth_ready = self._manager._collect_auth_ready("opencode")  # noqa: SLF001
                self._manager._finalize_active_session(session)  # noqa: SLF001
            except Exception as exc:
                session.status = "failed"
                session.error = str(exc)
                session.auth_ready = self._manager._collect_auth_ready("opencode")  # noqa: SLF001
                self._manager._finalize_active_session(session)  # noqa: SLF001
            return
        if isinstance(runtime, OpencodeGoogleAntigravityOAuthProxySession):
            self._manager._mark_manual_fallback(session)  # noqa: SLF001
            session.status = "code_submitted_waiting_result"
            session.updated_at = _utc_now()
            try:
                flow_result = self._manager._opencode_google_antigravity_oauth_proxy_flow.submit_input(runtime, value)  # noqa: SLF001
                session.status = "succeeded"
                session.error = None
                session.auth_ready = self._manager._collect_auth_ready("opencode")  # noqa: SLF001
                audit = self._manager._ensure_audit_dict(session)  # noqa: SLF001
                audit.update(flow_result)
                audit["callback_mode"] = "manual"
                self._manager._finalize_active_session(session)  # noqa: SLF001
            except Exception as exc:
                session.status = "failed"
                session.error = str(exc)
                session.auth_ready = self._manager._collect_auth_ready("opencode")  # noqa: SLF001
                self._manager._finalize_active_session(session)  # noqa: SLF001
            return
        if isinstance(runtime, OpenAIDeviceProxySession):
            raise ValueError("OpenCode OpenAI auth_code_or_url device session does not accept manual input")
        if runtime is None or not isinstance(runtime, OpencodeAuthCliSession):
            raise ValueError("Input is only supported for active delegated auth sessions")
        self._manager._opencode_flow.submit_input(runtime, value)  # noqa: SLF001

    def submit_legacy_input(self, session: Any, value: str) -> bool:
        return False

    def refresh_session_locked(self, session: Any) -> bool:
        runtime = session.driver_state
        if session.driver == "opencode":
            now = _utc_now()
            session.updated_at = now
            if session.status in _TERMINAL_STATUSES:
                session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
                return True
            if now > session.expires_at:
                self._manager._terminate_process(session)  # noqa: SLF001
                session.status = "expired"
                session.error = "Auth session expired"
                session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
                self._manager._finalize_active_session(session)  # noqa: SLF001
                return True
            if runtime is None:
                session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
                return True
            if not isinstance(runtime, OpencodeAuthCliSession):
                session.status = "failed"
                session.error = "OpenCode auth session driver is missing"
                session.auth_ready = False
                self._manager._finalize_active_session(session)  # noqa: SLF001
                return True
            self._manager._opencode_flow.refresh(runtime)  # noqa: SLF001
            session.updated_at = runtime.updated_at
            session.status = runtime.status
            session.auth_url = runtime.auth_url
            session.user_code = runtime.user_code
            session.error = runtime.error
            session.exit_code = runtime.exit_code
            session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
            if session.status == "failed" and session.exit_code == 0 and session.auth_ready:
                session.status = "succeeded"
                session.error = None
            if session.status in _TERMINAL_STATUSES:
                self._manager._finalize_active_session(session)  # noqa: SLF001
            return True
        if session.driver == "opencode_openai_oauth_proxy":
            if runtime is None or not isinstance(runtime, OpencodeOpenAIOAuthProxySession):
                session.status = "failed"
                session.error = "OpenCode OpenAI OAuth proxy session driver is missing"
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
        if session.driver == "opencode_google_antigravity_oauth_proxy":
            if runtime is None or not isinstance(runtime, OpencodeGoogleAntigravityOAuthProxySession):
                session.status = "failed"
                session.error = "OpenCode Google OAuth proxy session driver is missing"
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
        if session.driver == "opencode_openai_device_oauth_proxy":
            if runtime is None or not isinstance(runtime, OpenAIDeviceProxySession):
                session.status = "failed"
                session.error = "OpenCode OpenAI device auth session driver is missing"
                session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
                self._manager._finalize_active_session(session)  # noqa: SLF001
                return True
            if session.status in _TERMINAL_STATUSES:
                session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
                return True
            now = _utc_now()
            session.updated_at = now
            runtime.updated_at = now
            if now > session.expires_at:
                session.status = "expired"
                session.error = "Auth session expired"
                session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
                self._manager._finalize_active_session(session)  # noqa: SLF001
                return True
            if session.status == "starting":
                session.status = "waiting_user"
            try:
                tokens = self._manager._openai_device_proxy_flow.poll_once(runtime, now=now)  # noqa: SLF001
                if tokens is None:
                    session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
                    return True
                self._manager._opencode_openai_oauth_proxy_flow.complete_with_tokens(tokens)  # noqa: SLF001
                session.status = "succeeded"
                session.error = None
                session.auth_ready = self._manager._collect_auth_ready("opencode")  # noqa: SLF001
                self._manager._mark_auto_callback_success(session)  # noqa: SLF001
                self._manager._finalize_active_session(session)  # noqa: SLF001
            except Exception as exc:
                session.status = "failed"
                session.error = self._manager._build_openai_device_error_message(exc)  # noqa: SLF001
                session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
                self._manager._finalize_active_session(session)  # noqa: SLF001
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
        if channel == "openai" and session.engine == "opencode":
            runtime = session.driver_state
            if runtime is None or not isinstance(runtime, OpencodeOpenAIOAuthProxySession):
                return False
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
                self._manager._opencode_openai_oauth_proxy_flow.complete_with_code(runtime, normalized_code)  # noqa: SLF001
                session.auth_ready = self._manager._collect_auth_ready("opencode")  # noqa: SLF001
                session.status = "succeeded"
                session.error = None
                self._manager._mark_auto_callback_success(session)  # noqa: SLF001
            except Exception as exc:
                session.status = "failed"
                session.error = f"OAuth callback token exchange failed: {exc}"
                session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
            self._manager._finalize_active_session(session)  # noqa: SLF001
            return True
        if channel == "antigravity" and session.engine == "opencode":
            runtime = session.driver_state
            if runtime is None or not isinstance(runtime, OpencodeGoogleAntigravityOAuthProxySession):
                return False
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
                flow_result = self._manager._opencode_google_antigravity_oauth_proxy_flow.complete_with_code(  # noqa: SLF001
                    runtime=runtime,
                    code=normalized_code,
                    state=state,
                )
                session.status = "succeeded"
                session.error = None
                session.auth_ready = self._manager._collect_auth_ready("opencode")  # noqa: SLF001
                self._manager._mark_auto_callback_success(session)  # noqa: SLF001
                audit = self._manager._ensure_audit_dict(session)  # noqa: SLF001
                audit.update(flow_result)
                audit["callback_mode"] = "auto"
            except Exception as exc:
                session.status = "failed"
                session.error = f"OAuth callback token exchange failed: {exc}"
                session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
            self._manager._finalize_active_session(session)  # noqa: SLF001
            return True
        return False

    def terminate_session(self, session: Any) -> bool:
        runtime = session.driver_state
        if session.driver == "opencode" and runtime is not None and isinstance(runtime, OpencodeAuthCliSession):
            self._manager._opencode_flow.cancel(runtime)  # noqa: SLF001
            return True
        return False

    def on_session_finalizing(self, session: Any) -> None:
        self._rollback_google_antigravity_if_needed(session)
        runtime = session.driver_state
        if isinstance(runtime, OpencodeOpenAIOAuthProxySession):
            self._manager.unregister_callback_state(channel="openai", state=runtime.state)  # noqa: SLF001
        if isinstance(runtime, OpencodeGoogleAntigravityOAuthProxySession):
            self._manager.unregister_callback_state(channel="antigravity", state=runtime.state)  # noqa: SLF001
        if session.transport == _DEFAULT_TRANSPORT and session.driver == "opencode_openai_oauth_proxy":
            self._manager.stop_callback_listener(channel="openai")  # noqa: SLF001
        if session.transport == _DEFAULT_TRANSPORT and session.driver == "opencode_google_antigravity_oauth_proxy":
            self._manager.stop_callback_listener(channel="antigravity")  # noqa: SLF001

    def _rollback_google_antigravity_if_needed(self, session: Any) -> None:
        if session.engine != "opencode" or session.provider_id != "google":
            return
        audit = session.audit
        if not isinstance(audit, dict):
            return
        cleanup = audit.get("google_antigravity_cleanup")
        if not isinstance(cleanup, dict):
            return
        if session.status == "succeeded":
            return
        if cleanup.get("rollback_attempted"):
            return
        source_exists = bool(cleanup.get("source_exists"))
        backup_path = cleanup.get("backup_path")
        try:
            auth_store = self._manager._build_opencode_auth_store()  # noqa: SLF001
            auth_store.restore_antigravity_accounts(
                source_exists=source_exists,
                backup_path=backup_path if isinstance(backup_path, str) else None,
            )
            cleanup["rollback_attempted"] = True
            cleanup["rollback_success"] = True
        except Exception as exc:
            cleanup["rollback_attempted"] = True
            cleanup["rollback_success"] = False
            cleanup["rollback_error"] = str(exc)
            session.error = (
                f"{session.error} | rollback_failed: {exc}"
                if session.error
                else f"rollback_failed: {exc}"
            )
