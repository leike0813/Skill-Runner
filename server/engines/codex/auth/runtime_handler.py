from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ....config import config
from ....runtime.auth.session_lifecycle import AuthStartPlan, StartRuntimeContext
from ...common.openai_auth import OpenAIDeviceProxySession
from .oauth_proxy import CodexOAuthProxySession

_DEFAULT_TRANSPORT = "oauth_proxy"
_AUTH_METHOD_CALLBACK = "callback"
_AUTH_METHOD_AUTH_CODE_OR_URL = "auth_code_or_url"
_TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "expired"}
_OPENAI_DEVICE_USER_AGENT_CODEX = "codex-cli-rs/skill-runner"
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


class CodexAuthRuntimeHandler:
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
            raise ValueError("provider_id is not supported for codex auth sessions")
        if auth_method is None:
            effective_auth_method = _AUTH_METHOD_CALLBACK
        elif auth_method in {_AUTH_METHOD_CALLBACK, _AUTH_METHOD_AUTH_CODE_OR_URL}:
            effective_auth_method = auth_method
        else:
            raise ValueError("Unsupported auth_method for codex: use callback or auth_code_or_url")

        if not driver_registry.supports(
            transport=transport,
            engine="codex",
            auth_method=effective_auth_method,
            provider_id=None,
        ):
            raise ValueError(
                "Unsupported auth combination: "
                f"transport={transport}, engine=codex, auth_method={effective_auth_method}, provider_id=-"
            )
        requires_command = transport != _DEFAULT_TRANSPORT
        command = resolve_engine_command("codex") if requires_command else None
        if requires_command and command is None:
            raise RuntimeError("codex CLI not found")
        return AuthStartPlan(
            engine="codex",
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
                    raise ValueError("Codex callback mode requires local callback listener on localhost:1455")
                cleanup_state = context.cleanup_state if context.cleanup_state is not None else {}
                context.cleanup_state = cleanup_state
                cleanup_state["openai_listener_started"] = True
                runtime = self._manager._codex_oauth_proxy_flow.start_session(  # noqa: SLF001
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
                    engine="codex",
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
                    driver="codex_oauth_proxy",
                    driver_state=runtime,
                    execution_mode="protocol_proxy",
                    trust_engine=context.trust_engine,
                    trust_path=context.trust_path,
                    audit={
                        "manual_fallback_used": False,
                        "auto_callback_success": False,
                        "local_callback_listener_started": True,
                        "auto_callback_listener_started": True,
                    },
                )
            try:
                runtime = self._manager._openai_device_proxy_flow.start_session(  # noqa: SLF001
                    session_id=context.session_id,
                    now=context.now,
                    user_agent=_OPENAI_DEVICE_USER_AGENT_CODEX,
                )
            except Exception as exc:
                raise self._manager._build_openai_device_start_error(exc) from exc  # noqa: SLF001
            return self._manager._new_session(  # noqa: SLF001
                session_id=context.session_id,
                engine="codex",
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
                process=None,
                auth_url=runtime.verification_url,
                user_code=runtime.user_code,
                driver="codex_device_oauth_proxy",
                driver_state=runtime,
                execution_mode="protocol_proxy",
                trust_engine=context.trust_engine,
                trust_path=context.trust_path,
                audit={
                    "manual_fallback_used": False,
                    "auto_callback_success": False,
                    "local_callback_listener_started": False,
                },
            )

        command = plan.command
        if command is None:
            raise RuntimeError("codex CLI not found")
        args = [str(command), "login"]
        if plan.auth_method == _AUTH_METHOD_AUTH_CODE_OR_URL:
            args.append("--device-auth")
        with context.output_path.open("w", encoding="utf-8") as stream:
            process = subprocess.Popen(
                args,
                cwd=str(context.session_dir),
                env=context.env,
                stdin=subprocess.PIPE,
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
        return self._manager._new_session(  # noqa: SLF001
            session_id=context.session_id,
            engine="codex",
            method=plan.method,
            auth_method=plan.auth_method,
            transport=plan.transport,
            provider_id=None,
            provider_name=None,
            created_at=context.now,
            updated_at=context.now,
            expires_at=context.expires_at,
            status="starting",
            input_kind=("text" if plan.auth_method == _AUTH_METHOD_CALLBACK else None),
            output_path=context.output_path,
            process=process,
            driver="codex",
            execution_mode="cli_delegate",
            trust_engine=context.trust_engine,
            trust_path=context.trust_path,
        )

    def cleanup_start_error(self, *, context: StartRuntimeContext) -> None:
        if context.cleanup_state and context.cleanup_state.get("openai_listener_started"):
            self._manager.stop_callback_listener(channel="openai")  # noqa: SLF001

    def handle_input(self, session: Any, kind: str, value: str) -> None:
        if kind not in {"code", "text"}:
            raise ValueError("Codex auth only accepts code/text input")
        runtime = session.driver_state
        if isinstance(runtime, CodexOAuthProxySession):
            self._manager._mark_manual_fallback(session)  # noqa: SLF001
            session.status = "code_submitted_waiting_result"
            session.updated_at = _utc_now()
            try:
                self._manager._codex_oauth_proxy_flow.submit_input(runtime, value)  # noqa: SLF001
                session.status = "succeeded"
                session.error = None
                session.auth_ready = self._manager._collect_auth_ready("codex")  # noqa: SLF001
                self._manager._finalize_active_session(session)  # noqa: SLF001
            except Exception as exc:
                session.status = "failed"
                session.error = str(exc)
                session.auth_ready = self._manager._collect_auth_ready("codex")  # noqa: SLF001
                self._manager._finalize_active_session(session)  # noqa: SLF001
        elif isinstance(runtime, OpenAIDeviceProxySession):
            raise ValueError("Codex auth_code_or_url device session does not accept manual input")
        else:
            self.submit_legacy_input(session, value)

    def submit_legacy_input(self, session: Any, value: str) -> bool:
        if session.driver != "codex":
            return False
        normalized = value.strip()
        if not normalized:
            raise ValueError("Input value is required")
        process = session.process
        if process is None or process.poll() is not None:
            raise ValueError("Codex auth session is not active")
        stdin = process.stdin
        if stdin is None:
            raise ValueError("Codex auth session does not accept input")
        try:
            stdin.write(normalized + "\n")
            stdin.flush()
        except Exception as exc:
            raise ValueError(f"Failed to submit input to codex auth session: {exc}") from exc
        session.status = "code_submitted_waiting_result"
        session.updated_at = _utc_now()
        return True

    def refresh_session_locked(self, session: Any) -> bool:
        if session.driver == "codex_oauth_proxy":
            return self._refresh_codex_oauth_proxy_session_locked(session)
        if session.driver == "codex_device_oauth_proxy":
            return self._refresh_codex_device_oauth_proxy_session_locked(session)
        return False

    def _refresh_codex_oauth_proxy_session_locked(self, session: Any) -> bool:
        runtime = session.driver_state
        if runtime is None or not isinstance(runtime, CodexOAuthProxySession):
            session.status = "failed"
            session.error = "Codex OAuth proxy session driver is missing"
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

    def _refresh_codex_device_oauth_proxy_session_locked(self, session: Any) -> bool:
        runtime = session.driver_state
        if runtime is None or not isinstance(runtime, OpenAIDeviceProxySession):
            session.status = "failed"
            session.error = "Codex OpenAI device auth session driver is missing"
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
            self._manager._codex_oauth_proxy_flow.complete_with_tokens(tokens)  # noqa: SLF001
            session.status = "succeeded"
            session.error = None
            session.auth_ready = self._manager._collect_auth_ready("codex")  # noqa: SLF001
            self._manager._mark_auto_callback_success(session)  # noqa: SLF001
            self._manager._finalize_active_session(session)  # noqa: SLF001
        except Exception as exc:
            session.status = "failed"
            session.error = self._manager._build_openai_device_error_message(exc)  # noqa: SLF001
            session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
            self._manager._finalize_active_session(session)  # noqa: SLF001
        return True

    def complete_callback(
        self,
        *,
        channel: str,
        session: Any,
        state: str,
        code: str | None,
        error: str | None,
    ) -> bool:
        if channel != "openai" or session.engine != "codex":
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
        runtime = session.driver_state
        if runtime is None or not isinstance(runtime, CodexOAuthProxySession):
            session.status = "failed"
            session.error = "OAuth callback session does not support OpenAI callback"
            session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
            self._manager._finalize_active_session(session)  # noqa: SLF001
            return True
        try:
            self._manager._codex_oauth_proxy_flow.complete_with_code(runtime, normalized_code)  # noqa: SLF001
            session.auth_ready = self._manager._collect_auth_ready("codex")  # noqa: SLF001
            session.status = "succeeded"
            session.error = None
            self._manager._mark_auto_callback_success(session)  # noqa: SLF001
        except Exception as exc:
            session.status = "failed"
            session.error = f"OAuth callback token exchange failed: {exc}"
            session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
        self._manager._finalize_active_session(session)  # noqa: SLF001
        return True

    def terminate_session(self, session: Any) -> bool:
        return False

    def on_session_finalizing(self, session: Any) -> None:
        runtime = session.driver_state
        if isinstance(runtime, CodexOAuthProxySession):
            self._manager.unregister_callback_state(channel="openai", state=runtime.state)  # noqa: SLF001
        if session.transport == _DEFAULT_TRANSPORT and session.driver == "codex_oauth_proxy":
            self._manager.stop_callback_listener(channel="openai")  # noqa: SLF001
