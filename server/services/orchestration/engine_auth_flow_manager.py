import json
import os
import platform
import re
import signal
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional, Protocol, cast
from urllib.parse import urlsplit

from server.config import config
from server.engines.common.openai_auth import OpenAIDeviceProxySession, OpenAIOAuthError
from server.engines.opencode.auth import OpencodeAuthStore
from server.runtime.auth.callbacks import CallbackStateStore
from server.runtime.auth.log_writer import AuthLogWriter, TransportLogPaths
from server.runtime.auth.session_lifecycle import (
    AuthSessionCallbackCompleter,
    AuthSessionInputHandler,
    AuthSessionRefresher,
    AuthSessionStartPlanner,
    AuthSessionStarter,
)
from server.runtime.auth.session_store import AuthSessionStore, SessionPointer
from server.services.orchestration.agent_cli_manager import AgentCliManager
from server.services.orchestration.engine_auth_bootstrap import build_engine_auth_bootstrap
from server.services.orchestration.engine_interaction_gate import (
    EngineInteractionBusyError,
    EngineInteractionGate,
    engine_interaction_gate,
)
from server.services.orchestration.run_folder_trust_manager import run_folder_trust_manager

_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_CODE_PATTERN = re.compile(r"\b[A-Z0-9]{4}(?:-[A-Z0-9]{4,})+\b")
_TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "expired"}
_DEFAULT_TRANSPORT = "oauth_proxy"
_ANSI_CSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_ANSI_OSC_PATTERN = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(value: datetime | None = None) -> str:
    now = value or _utc_now()
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def _strip_ansi(text: str) -> str:
    cleaned = _ANSI_OSC_PATTERN.sub("", text)
    cleaned = _ANSI_CSI_PATTERN.sub("", cleaned)
    return cleaned


@dataclass
class _AuthSession:
    session_id: str
    engine: str
    method: str
    auth_method: str
    transport: str
    provider_id: Optional[str]
    provider_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    status: str
    input_kind: Optional[str] = None
    output_path: Path | None = None
    process: subprocess.Popen[Any] | None = None
    auth_url: Optional[str] = None
    user_code: Optional[str] = None
    error: Optional[str] = None
    auth_ready: bool = False
    exit_code: Optional[int] = None
    driver: str = "codex"
    driver_state: Any = None
    execution_mode: str = "cli_delegate"
    manual_fallback_used: bool = False
    oauth_callback_received: bool = False
    oauth_callback_at: Optional[str] = None
    audit: Dict[str, Any] | None = None
    trust_engine: Optional[str] = None
    trust_path: Optional[Path] = None
    log_root: Path | None = None
    log_paths: TransportLogPaths | None = None


class TrustManagerProtocol(Protocol):
    def register_run_folder(self, engine: str, run_dir: Path) -> None:
        ...

    def remove_run_folder(self, engine: str, run_dir: Path) -> None:
        ...

    def bootstrap_parent_trust(self, runs_parent: Path) -> None:
        ...


class EngineAuthFlowManager:
    def __init__(
        self,
        agent_manager: AgentCliManager | None = None,
        interaction_gate: EngineInteractionGate | None = None,
        trust_manager: TrustManagerProtocol | None = None,
    ) -> None:
        self.agent_manager = agent_manager or AgentCliManager()
        self.interaction_gate = interaction_gate or engine_interaction_gate
        self.trust_manager = trust_manager or run_folder_trust_manager
        self._lock = Lock()
        self._sessions: Dict[str, _AuthSession] = {}
        self._active_session_id: Optional[str] = None
        bootstrap_bundle = build_engine_auth_bootstrap(
            self,
            agent_home=self.agent_manager.profile.agent_home,
        )
        self._driver_registry = bootstrap_bundle.driver_registry
        self._auth_log_writer = AuthLogWriter(self._session_root())
        self._session_store = AuthSessionStore()
        self._callback_state_store = CallbackStateStore()
        self._callback_listener_registry = bootstrap_bundle.callback_listener_registry
        self._engine_auth_handlers = bootstrap_bundle.engine_auth_handlers
        self._session_refresher = AuthSessionRefresher(
            self,
            handlers=cast(Any, self._engine_auth_handlers),
        )
        self._session_input_handler = AuthSessionInputHandler(
            self,
            handlers=cast(Any, self._engine_auth_handlers),
        )
        self._session_callback_completer = AuthSessionCallbackCompleter(
            self,
            handlers=cast(Any, self._engine_auth_handlers),
            state_store=self._callback_state_store,
        )
        self._session_start_planner = AuthSessionStartPlanner(
            self,
            planners=cast(Any, self._engine_auth_handlers),
        )
        self._session_starter = AuthSessionStarter(
            self,
            handlers=cast(Any, self._engine_auth_handlers),
        )

    def _enabled(self) -> bool:
        return bool(config.SYSTEM.ENGINE_AUTH_DEVICE_PROXY_ENABLED)

    def _new_session(self, **kwargs: Any) -> _AuthSession:  # noqa: ANN401
        return _AuthSession(**kwargs)

    def resolve_transport_start_method(
        self,
        *,
        transport: str,
        engine: str,
        auth_method: str,
        provider_id: str | None = None,
    ) -> str:
        _, driver_meta = self._driver_registry.resolve(
            transport=transport,
            engine=engine,
            auth_method=auth_method,
            provider_id=provider_id,
        )
        if isinstance(driver_meta, dict):
            start_method = driver_meta.get("start_method")
            if isinstance(start_method, str) and start_method.strip():
                return start_method.strip().lower()
        return "auth"

    def _ttl_seconds(self) -> int:
        raw = int(config.SYSTEM.ENGINE_AUTH_DEVICE_PROXY_TTL_SECONDS)
        return max(60, raw)

    def _session_root(self) -> Path:
        return self.agent_manager.profile.data_dir / "engine_auth_sessions"

    def _transport_state_machine(self, transport: str) -> str:
        normalized = transport.strip().lower()
        if normalized == "oauth_proxy":
            return "oauth_proxy_v1"
        return "cli_delegate_v1"

    def _orchestrator_name(self, transport: str) -> str:
        normalized = transport.strip().lower()
        if normalized == "oauth_proxy":
            return "oauth_proxy_orchestrator"
        return "cli_delegate_orchestrator"

    def _append_session_event(
        self,
        session: _AuthSession,
        event_type: str,
        payload: Dict[str, Any] | None = None,
    ) -> None:
        if session.log_paths is None:
            return
        self._auth_log_writer.append_event(session.log_paths, event_type, payload)

    def _try_settle_active_session_before_new_start_locked(self, session: _AuthSession) -> None:
        """
        Reduce stale-active windows for oauth_proxy auth_code_or_url device flows.

        If user finishes authorization and immediately triggers a new auth start,
        interval-gated polling may not have run yet, leaving the previous session
        in waiting_user. Force one extra poll cycle before declaring busy.
        """
        if session.status in _TERMINAL_STATUSES:
            return
        if session.driver not in {"codex_device_oauth_proxy", "opencode_openai_device_oauth_proxy"}:
            return
        runtime = session.driver_state
        if runtime is None or not isinstance(runtime, OpenAIDeviceProxySession):
            return
        runtime.next_poll_at = _utc_now()
        self._append_session_event(
            session,
            "forced_poll_for_new_start",
            {"reason": "settle_active_device_session"},
        )
        self._refresh_session_locked(session)

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _prepare_gemini_auth_workspace(self, session_dir: Path) -> None:
        self._write_json(
            session_dir / ".gemini" / "settings.json",
            {
                "general": {
                    "enableAutoUpdate": False,
                },
            },
        )

    def _build_opencode_auth_store(self) -> OpencodeAuthStore:
        return OpencodeAuthStore(self.agent_manager.profile.agent_home)

    def register_callback_state(self, *, channel: str, session_id: str, state: str) -> None:
        self._callback_state_store.register(
            channel=channel,
            state=state,
            session_id=session_id,
        )

    def unregister_callback_state(self, *, channel: str, state: str) -> None:
        self._callback_state_store.unregister(channel=channel, state=state)

    def start_callback_listener(
        self,
        *,
        channel: str,
        callback_handler: Any,
    ) -> tuple[bool, str | None]:
        result = self._callback_listener_registry.start(
            channel=channel,
            callback_handler=callback_handler,
        )
        return result.started, result.endpoint

    def stop_callback_listener(self, *, channel: str) -> None:
        self._callback_listener_registry.stop(channel=channel)

    def _engine_handler_for(self, engine: str) -> Any:
        return self._engine_auth_handlers.get(engine.strip().lower())

    def _inject_trust_for_session(self, engine: str, session_dir: Path) -> tuple[str, Path]:
        handler = self._engine_handler_for(engine)
        requires_parent_bootstrap = False
        if handler is not None:
            check_fn = getattr(handler, "requires_parent_trust_bootstrap", None)
            if callable(check_fn):
                requires_parent_bootstrap = bool(check_fn())
        if requires_parent_bootstrap:
            self.trust_manager.bootstrap_parent_trust(self._session_root())
        self.trust_manager.register_run_folder(engine, session_dir)
        return engine, session_dir

    def _cleanup_trust_for_session(self, session: _AuthSession) -> None:
        if not session.trust_engine or not session.trust_path:
            return
        try:
            self.trust_manager.remove_run_folder(session.trust_engine, session.trust_path)
        except Exception:
            pass
        finally:
            session.trust_engine = None
            session.trust_path = None

    def _finalize_active_session(self, session: _AuthSession) -> None:
        self._append_session_event(
            session,
            "session_finished",
            {
                "status": session.status,
                "error": session.error,
                "auth_ready": bool(session.auth_ready),
            },
        )
        handler = self._engine_handler_for(session.engine)
        if handler is not None:
            finalize_hook = getattr(handler, "on_session_finalizing", None)
            if callable(finalize_hook):
                finalize_hook(session)
        if self._active_session_id == session.session_id:
            self._active_session_id = None
        self._session_store.clear_active(session.transport, session.session_id)
        self.interaction_gate.release("auth_flow", session.session_id)
        self._cleanup_trust_for_session(session)

    def _read_output_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return ""
        except Exception:
            return ""

    def _extract_auth_url(self, text: str) -> Optional[str]:
        sanitized = _strip_ansi(text)
        matches = [
            match.group(0).strip().rstrip(".,);")
            for match in _URL_PATTERN.finditer(sanitized)
        ]
        if not matches:
            return None
        for candidate in reversed(matches):
            try:
                host = (urlsplit(candidate).hostname or "").lower()
            except Exception:
                host = ""
            if host not in {"localhost", "127.0.0.1", "::1"}:
                return candidate
        return matches[-1]

    def _extract_user_code(self, text: str) -> Optional[str]:
        sanitized = _strip_ansi(text)
        for line in sanitized.splitlines():
            lowered = line.lower()
            if "code" not in lowered and "device" not in lowered and "enter" not in lowered:
                continue
            match = _CODE_PATTERN.search(line.upper())
            if match:
                return match.group(0)
        match = _CODE_PATTERN.search(sanitized.upper())
        if match:
            return match.group(0)
        return None

    def _build_error_summary(self, text: str, fallback: str) -> str:
        sanitized = _strip_ansi(text)
        rows = [line.strip() for line in sanitized.splitlines() if line.strip()]
        if not rows:
            return fallback
        tail = rows[-3:]
        return " | ".join(tail)

    def _collect_auth_ready(self, engine: str) -> bool:
        snapshot = self.agent_manager.collect_auth_status().get(engine, {})
        return bool(snapshot.get("auth_ready"))

    def _build_openai_device_start_error(self, exc: Exception) -> ValueError:
        if isinstance(exc, OpenAIOAuthError) and exc.status_code is not None:
            return ValueError(
                f"OpenAI device-auth protocol request failed (HTTP {exc.status_code}). "
                "Please retry later or use callback / cli_delegate."
            )
        return ValueError(
            f"OpenAI device-auth protocol request failed: {exc}. "
            "Please retry later or use callback / cli_delegate."
        )

    def _build_openai_device_error_message(self, exc: Exception) -> str:
        if isinstance(exc, OpenAIOAuthError) and exc.status_code is not None:
            return (
                f"OpenAI device-auth polling failed (HTTP {exc.status_code}): {exc}. "
                "Please retry or switch to callback / cli_delegate."
            )
        return f"OpenAI device-auth polling failed: {exc}"

    def _ensure_audit_dict(self, session: _AuthSession) -> Dict[str, Any]:
        if session.audit is None:
            session.audit = {}
        return session.audit

    def _mark_manual_fallback(self, session: _AuthSession) -> None:
        session.manual_fallback_used = True
        audit = self._ensure_audit_dict(session)
        audit["manual_fallback_used"] = True

    def _mark_auto_callback_success(self, session: _AuthSession) -> None:
        if session.transport != _DEFAULT_TRANSPORT:
            return
        audit = self._ensure_audit_dict(session)
        if not audit.get("manual_fallback_used"):
            audit["auto_callback_success"] = True

    def _mark_oauth_callback_received(self, session: _AuthSession) -> None:
        timestamp = _utc_iso()
        session.oauth_callback_received = True
        session.oauth_callback_at = timestamp
        audit = self._ensure_audit_dict(session)
        audit["oauth_callback_received"] = True
        audit["oauth_callback_at"] = timestamp
        self._append_session_event(
            session,
            "callback_received",
            {
                "oauth_callback_at": timestamp,
                "stateful": True,
            },
        )

    def _refresh_session_locked(self, session: _AuthSession) -> None:
        self._session_refresher.refresh_session_locked(session)

    def _terminate_process(self, session: _AuthSession) -> None:
        handler = self._engine_handler_for(session.engine)
        if handler is not None:
            terminate_hook = getattr(handler, "terminate_session", None)
            if callable(terminate_hook) and bool(terminate_hook(session)):
                return
        proc = session.process
        if proc is None:
            return
        if proc.poll() is not None:
            return
        try:
            if platform.system().lower().startswith("win"):
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            else:
                os.killpg(proc.pid, signal.SIGTERM)
                deadline = time.monotonic() + 2.5
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.05)
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            pass

    def _to_snapshot(self, session: _AuthSession) -> Dict[str, Any]:
        transport_state_machine = self._transport_state_machine(session.transport)
        orchestrator = self._orchestrator_name(session.transport)
        log_root = str(session.log_root) if session.log_root is not None else None
        return {
            "session_id": session.session_id,
            "engine": session.engine,
            "method": session.method,
            "auth_method": session.auth_method,
            "transport": session.transport,
            "provider_id": session.provider_id,
            "provider_name": session.provider_name,
            "status": session.status,
            "input_kind": session.input_kind,
            "auth_url": session.auth_url,
            "user_code": session.user_code,
            "created_at": _utc_iso(session.created_at),
            "updated_at": _utc_iso(session.updated_at),
            "expires_at": _utc_iso(session.expires_at),
            "auth_ready": bool(session.auth_ready),
            "error": session.error,
            "exit_code": session.exit_code,
            "execution_mode": session.execution_mode,
            "manual_fallback_used": bool(session.manual_fallback_used),
            "oauth_callback_received": bool(session.oauth_callback_received),
            "oauth_callback_at": session.oauth_callback_at,
            "transport_state_machine": transport_state_machine,
            "orchestrator": orchestrator,
            "log_root": log_root,
            "deprecated": False,
            "audit": session.audit,
            "terminal": session.status in _TERMINAL_STATUSES,
        }

    def get_active_session_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            if not self._active_session_id:
                return {"active": False}
            session = self._sessions.get(self._active_session_id)
            if session is None:
                self._active_session_id = None
                return {"active": False}
            self._refresh_session_locked(session)
            active = session.status not in _TERMINAL_STATUSES
            payload = self._to_snapshot(session)
            payload["active"] = active
            return payload

    def start_session(
        self,
        engine: str,
        method: str = "auth",
        auth_method: str | None = None,
        provider_id: str | None = None,
        transport: str | None = None,
        callback_base_url: str | None = None,
    ) -> Dict[str, Any]:
        if not self._enabled():
            raise ValueError("Engine auth device proxy is disabled")
        plan = self._session_start_planner.plan_start(
            engine=engine,
            method=method,
            auth_method=auth_method,
            provider_id=provider_id,
            transport=transport,
        )
        normalized_engine = plan.engine
        session_id = str(uuid.uuid4())
        with self._lock:
            if self._active_session_id:
                active = self._sessions.get(self._active_session_id)
                if active is not None:
                    self._refresh_session_locked(active)
                    self._try_settle_active_session_before_new_start_locked(active)
                    if active.status not in _TERMINAL_STATUSES:
                        raise EngineInteractionBusyError(
                            f"Auth session already active: {active.session_id}"
                        )
                self._active_session_id = None

            self.interaction_gate.acquire(
                "auth_flow",
                session_id=session_id,
                engine=normalized_engine,
            )
            return self._session_starter.start_from_plan_locked(
                plan=plan,
                session_id=session_id,
                callback_base_url=callback_base_url,
            )

    def complete_callback(
        self,
        *,
        channel: str,
        state: str,
        code: str | None = None,
        error: str | None = None,
        ) -> Dict[str, Any]:
        return self._session_callback_completer.complete_callback(
            channel=channel,
            state=state,
            code=code,
            error=error,
        )

    def get_session(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            self._refresh_session_locked(session)
            return self._to_snapshot(session)

    def cancel_session(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            self._refresh_session_locked(session)
            if session.status not in _TERMINAL_STATUSES:
                termination_error: str | None = None
                try:
                    self._terminate_process(session)
                except Exception as exc:  # pragma: no cover - defensive release path
                    termination_error = str(exc)
                session.status = "canceled"
                session.updated_at = _utc_now()
                session.auth_ready = (
                    self._collect_auth_ready(session.engine)
                    if session.engine in {"codex", "opencode"}
                    else False
                )
                session.error = session.error or "Canceled by user"
                if termination_error:
                    session.error = f"{session.error} (terminate error: {termination_error})"
                self._finalize_active_session(session)
            return self._to_snapshot(session)

    def input_session(self, session_id: str, kind: str, value: str) -> Dict[str, Any]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            self._refresh_session_locked(session)
            return self._session_input_handler.handle_input(session, kind, value)


engine_auth_flow_manager = EngineAuthFlowManager()
