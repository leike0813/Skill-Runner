from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from .callbacks import CallbackStateStore
from .session_store import SessionPointer

_DEFAULT_TRANSPORT = "oauth_proxy"
_SUPPORTED_TRANSPORTS = {_DEFAULT_TRANSPORT, "cli_delegate"}
_TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "expired"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class AuthStartPlan:
    engine: str
    method: str
    auth_method: str
    transport: str
    provider_id: str | None
    provider: Any | None
    registry_provider_id: str | None
    command: Path | None
    requires_command: bool


@dataclass
class StartRuntimeContext:
    session_id: str
    session_dir: Path
    output_path: Path
    env: dict[str, str]
    now: datetime
    expires_at: datetime
    trust_engine: str | None = None
    trust_path: Path | None = None
    cleanup_state: dict[str, Any] | None = None


class EngineAuthPlanner(Protocol):
    def plan_start(
        self,
        *,
        method: str,
        auth_method: str | None,
        transport: str,
        provider_id: str | None,
        driver_registry: Any,
        resolve_engine_command: Callable[[str], Path | None],
    ) -> AuthStartPlan:
        ...


class EngineStartRuntimeHandler(Protocol):
    def start_session_locked(
        self,
        *,
        plan: AuthStartPlan,
        callback_base_url: str | None,
        context: StartRuntimeContext,
    ) -> Any:
        ...

    def cleanup_start_error(self, *, context: StartRuntimeContext) -> None:
        ...


class EngineRefreshRuntimeHandler(Protocol):
    def refresh_session_locked(self, session: Any) -> bool:
        ...

    def submit_legacy_input(self, session: Any, value: str) -> bool:
        ...


class EngineInputRuntimeHandler(Protocol):
    def handle_input(self, session: Any, kind: str, value: str) -> None:
        ...


class EngineCallbackRuntimeHandler(Protocol):
    def complete_callback(
        self,
        *,
        channel: str,
        session: Any,
        state: str,
        code: str | None,
        error: str | None,
    ) -> bool:
        ...


class AuthSessionStartPlanner:
    def __init__(self, manager: Any, planners: Mapping[str, EngineAuthPlanner]) -> None:
        self._manager = manager
        self._planners = planners

    def plan_start(
        self,
        *,
        engine: str,
        method: str = "auth",
        auth_method: str | None = None,
        provider_id: str | None = None,
        transport: str | None = None,
    ) -> AuthStartPlan:
        normalized_engine = engine.strip().lower()
        planner = self._planners.get(normalized_engine)
        if planner is None:
            raise ValueError("Unsupported engine for auth proxy")

        normalized_method = method.strip().lower()
        normalized_auth_method = (
            auth_method.strip().lower() if isinstance(auth_method, str) and auth_method.strip() else None
        )
        normalized_transport = (
            transport.strip().lower() if isinstance(transport, str) and transport.strip() else _DEFAULT_TRANSPORT
        )
        if normalized_transport not in _SUPPORTED_TRANSPORTS:
            raise ValueError(
                f"Unsupported transport: {normalized_transport}. Expected one of: oauth_proxy, cli_delegate"
            )
        normalized_provider = provider_id.strip().lower() if provider_id else None

        return planner.plan_start(
            method=normalized_method,
            auth_method=normalized_auth_method,
            transport=normalized_transport,
            provider_id=normalized_provider,
            driver_registry=self._manager._driver_registry,  # noqa: SLF001
            resolve_engine_command=lambda e: self._manager.agent_manager.resolve_engine_command(e),  # noqa: SLF001
        )


class AuthSessionStarter:
    def __init__(self, manager: Any, handlers: Mapping[str, EngineStartRuntimeHandler]) -> None:
        self._manager = manager
        self._handlers = handlers

    def start_from_plan_locked(
        self,
        *,
        plan: AuthStartPlan,
        session_id: str,
        callback_base_url: str | None = None,
    ) -> dict[str, Any]:
        log_paths = self._manager._auth_log_writer.init_paths(  # noqa: SLF001
            transport=plan.transport,
            session_id=session_id,
        )
        session_dir = log_paths.root
        output_path = log_paths.primary_log_path
        env = self._manager.agent_manager.profile.build_subprocess_env(os.environ.copy())
        env.setdefault("TERM", "xterm-256color")
        now = _utc_now()
        context = StartRuntimeContext(
            session_id=session_id,
            session_dir=session_dir,
            output_path=output_path,
            env=env,
            now=now,
            expires_at=now + timedelta(seconds=self._manager._ttl_seconds()),  # noqa: SLF001
            cleanup_state={},
        )

        try:
            context.trust_engine, context.trust_path = self._manager._inject_trust_for_session(  # noqa: SLF001
                plan.engine,
                session_dir,
            )
            handler = self._handlers.get(plan.engine)
            if handler is None:
                raise ValueError(f"No runtime handler registered for engine={plan.engine}")
            session = handler.start_session_locked(
                plan=plan,
                callback_base_url=callback_base_url,
                context=context,
            )
        except Exception:
            handler = self._handlers.get(plan.engine)
            if handler is not None:
                try:
                    handler.cleanup_start_error(context=context)
                except Exception:
                    pass
            if context.trust_engine and context.trust_path:
                try:
                    self._manager.trust_manager.remove_run_folder(context.trust_engine, context.trust_path)
                except Exception:
                    pass
            self._manager.interaction_gate.release("auth_flow", session_id)
            raise

        session.log_root = session_dir
        session.log_paths = log_paths
        self._manager._sessions[session_id] = session  # noqa: SLF001
        self._manager._session_store.upsert(  # noqa: SLF001
            SessionPointer(
                session_id=session_id,
                transport=plan.transport,
                engine=plan.engine,
                auth_method=plan.auth_method,
                provider_id=(plan.provider.provider_id if plan.provider is not None else None),
            )
        )
        self._manager._append_session_event(  # noqa: SLF001
            session,
            "session_started",
            {
                "status": session.status,
                "engine": session.engine,
                "auth_method": session.auth_method,
                "provider_id": session.provider_id,
            },
        )
        self._manager._active_session_id = session_id  # noqa: SLF001
        self._manager._refresh_session_locked(session)  # noqa: SLF001
        return self._manager._to_snapshot(session)  # noqa: SLF001


class AuthSessionRefresher:
    def __init__(self, manager: Any, handlers: Mapping[str, EngineRefreshRuntimeHandler]) -> None:
        self._manager = manager
        self._handlers = handlers

    def refresh_session_locked(self, session: Any) -> None:
        previous_status = session.status
        handler = self._handlers.get(str(session.engine).lower())
        if handler is not None and handler.refresh_session_locked(session):
            self._append_state_changed_if_needed(session, previous_status)
            return

        now = _utc_now()
        session.updated_at = now

        if session.status in _TERMINAL_STATUSES:
            session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
            self._append_state_changed_if_needed(session, previous_status)
            return

        if now > session.expires_at:
            self._manager._terminate_process(session)  # noqa: SLF001
            session.status = "expired"
            session.error = "Auth session expired"
            session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
            self._manager._finalize_active_session(session)  # noqa: SLF001
            self._append_state_changed_if_needed(session, previous_status)
            return

        if session.output_path is None or session.process is None:
            session.status = "failed"
            session.error = f"{session.engine} auth session is missing process context"
            session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
            self._manager._finalize_active_session(session)  # noqa: SLF001
            self._append_state_changed_if_needed(session, previous_status)
            return

        text = self._manager._read_output_text(session.output_path)  # noqa: SLF001
        auth_url = self._manager._extract_auth_url(text)  # noqa: SLF001
        if auth_url:
            session.auth_url = auth_url
        user_code = self._manager._extract_user_code(text)  # noqa: SLF001
        if user_code:
            session.user_code = user_code

        rc = session.process.poll()
        if rc is None:
            if session.status == "starting":
                session.status = "waiting_user"
            session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
            self._append_state_changed_if_needed(session, previous_status)
            return

        session.exit_code = rc
        session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
        if session.status == "canceled":
            pass
        elif session.auth_ready:
            session.status = "succeeded"
            session.error = None
            self._manager._mark_auto_callback_success(session)  # noqa: SLF001
        else:
            session.status = "failed"
            session.error = self._manager._build_error_summary(  # noqa: SLF001
                text,
                fallback=f"{session.engine} login exited with code {rc}",
            )
        self._manager._finalize_active_session(session)  # noqa: SLF001
        self._append_state_changed_if_needed(session, previous_status)

    def _append_state_changed_if_needed(self, session: Any, previous_status: str) -> None:
        if session.status != previous_status:
            self._manager._append_session_event(  # noqa: SLF001
                session,
                "state_changed",
                {"from": previous_status, "to": session.status},
            )


class AuthSessionInputHandler:
    def __init__(self, manager: Any, handlers: Mapping[str, EngineInputRuntimeHandler]) -> None:
        self._manager = manager
        self._handlers = handlers

    def handle_input(self, session: Any, kind: str, value: str) -> dict[str, Any]:
        normalized_kind = kind.strip().lower()
        if normalized_kind not in {"code", "api_key", "text"}:
            raise ValueError("Unsupported input kind")

        self._manager._append_session_event(  # noqa: SLF001
            session,
            "input_received",
            {
                "kind": normalized_kind,
                "value_redacted": True,
            },
        )
        handler = self._handlers.get(str(session.engine).lower())
        if handler is None:
            raise ValueError("Input is not supported for this auth session")
        handler.handle_input(session, normalized_kind, value)
        self._manager._refresh_session_locked(session)  # noqa: SLF001
        return self._manager._to_snapshot(session)  # noqa: SLF001


class AuthSessionCallbackCompleter:
    def __init__(
        self,
        manager: Any,
        handlers: Mapping[str, EngineCallbackRuntimeHandler],
        state_store: CallbackStateStore,
    ) -> None:
        self._manager = manager
        self._handlers = handlers
        self._state_store = state_store

    def complete_callback(
        self,
        *,
        channel: str,
        state: str,
        code: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        normalized_channel = channel.strip().lower()
        normalized_state = state.strip()
        with self._manager._lock:  # noqa: SLF001
            if self._state_store.is_consumed(channel=normalized_channel, state=normalized_state):
                raise ValueError("OAuth callback state has already been consumed")
            session_id = self._state_store.resolve_session_id(
                channel=normalized_channel,
                state=normalized_state,
            )
            if session_id is None:
                raise ValueError("OAuth callback state is invalid")
            session = self._manager._sessions.get(session_id)  # noqa: SLF001
            if session is None:
                self._state_store.consume(channel=normalized_channel, state=normalized_state)
                raise ValueError("OAuth callback session not found")

            self._manager._refresh_session_locked(session)  # noqa: SLF001
            if session.status in _TERMINAL_STATUSES:
                self._state_store.consume(channel=normalized_channel, state=normalized_state)
                raise ValueError("OAuth callback session is already finished")

            handler = self._handlers.get(str(session.engine).lower())
            if handler is None:
                self._state_store.consume(channel=normalized_channel, state=normalized_state)
                raise ValueError("OAuth callback session does not support this callback channel")

            self._state_store.consume(channel=normalized_channel, state=normalized_state)
            self._manager._mark_oauth_callback_received(session)  # noqa: SLF001
            session.updated_at = _utc_now()

            handled = handler.complete_callback(
                channel=normalized_channel,
                session=session,
                state=normalized_state,
                code=code,
                error=error,
            )
            if not handled:
                session.status = "failed"
                session.error = "OAuth callback session does not support this callback channel"
                session.auth_ready = self._manager._collect_auth_ready(session.engine)  # noqa: SLF001
                self._manager._finalize_active_session(session)  # noqa: SLF001
            return self._manager._to_snapshot(session)  # noqa: SLF001
