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
from typing import Any, Dict, Optional, Protocol
from urllib.parse import urlsplit

from ..config import config
from .auth_runtime.driver_registry import AuthDriverRegistry
from .auth_runtime.log_writer import AuthLogWriter, TransportLogPaths
from .auth_runtime.session_store import AuthSessionStore, SessionPointer
from .agent_cli_manager import AgentCliManager
from .codex_oauth_proxy_flow import CodexOAuthProxyFlow, CodexOAuthProxySession
from .engine_interaction_gate import (
    EngineInteractionBusyError,
    EngineInteractionGate,
    engine_interaction_gate,
)
from .gemini_auth_cli_flow import GeminiAuthCliFlow, GeminiAuthCliSession
from .gemini_oauth_proxy_flow import GeminiOAuthProxyFlow, GeminiOAuthProxySession
from .iflow_auth_cli_flow import IFlowAuthCliFlow, IFlowAuthCliSession
from .iflow_oauth_proxy_flow import IFlowOAuthProxyFlow, IFlowOAuthProxySession
from .openai_device_proxy_flow import OpenAIDeviceProxyFlow, OpenAIDeviceProxySession
from .opencode_auth_cli_flow import OpencodeAuthCliFlow, OpencodeAuthCliSession
from .opencode_google_antigravity_oauth_proxy_flow import (
    OpencodeGoogleAntigravityOAuthProxyFlow,
    OpencodeGoogleAntigravityOAuthProxySession,
)
from .opencode_openai_oauth_proxy_flow import (
    OpencodeOpenAIOAuthProxyFlow,
    OpencodeOpenAIOAuthProxySession,
)
from .opencode_auth_provider_registry import (
    OpencodeAuthProvider,
    opencode_auth_provider_registry,
)
from .opencode_auth_store import OpencodeAuthStore
from .oauth_openai_proxy_common import OpenAIOAuthError, OpenAITokenSet
from .run_folder_trust_manager import run_folder_trust_manager

_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_CODE_PATTERN = re.compile(r"\b[A-Z0-9]{4}(?:-[A-Z0-9]{4,})+\b")
_TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "expired"}
_DEFAULT_TRANSPORT = "oauth_proxy"
_SUPPORTED_TRANSPORTS = {_DEFAULT_TRANSPORT, "cli_delegate"}
_AUTH_METHOD_CALLBACK = "callback"
_AUTH_METHOD_AUTH_CODE_OR_URL = "auth_code_or_url"
_AUTH_METHOD_API_KEY = "api_key"
_ANSI_CSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_ANSI_OSC_PATTERN = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)")
_OPENAI_LOCAL_REDIRECT_URI = "http://localhost:1455/auth/callback"
_ANTIGRAVITY_LOCAL_REDIRECT_URI = "http://localhost:51121/oauth-callback"
_GEMINI_LOCAL_REDIRECT_URI = "http://localhost:51122/oauth2callback"
_IFLOW_LOCAL_REDIRECT_URI = "http://localhost:11451/oauth2callback"
_GEMINI_MANUAL_REDIRECT_URI = "https://codeassist.google.com/authcode"
_IFLOW_MANUAL_REDIRECT_URI = "https://iflow.cn/oauth/code-display"
_OPENAI_DEVICE_USER_AGENT_CODEX = "codex-cli-rs/skill-runner"
_OPENAI_DEVICE_USER_AGENT_OPENCODE = "opencode/skill-runner"


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
    driver_state: (
        GeminiAuthCliSession
        | IFlowAuthCliSession
        | OpencodeAuthCliSession
        | GeminiOAuthProxySession
        | IFlowOAuthProxySession
        | CodexOAuthProxySession
        | OpencodeOpenAIOAuthProxySession
        | OpencodeGoogleAntigravityOAuthProxySession
        | OpenAIDeviceProxySession
        | None
    ) = None
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
        self._gemini_flow = GeminiAuthCliFlow()
        self._gemini_oauth_proxy_flow = GeminiOAuthProxyFlow(self.agent_manager.profile.agent_home)
        self._iflow_oauth_proxy_flow = IFlowOAuthProxyFlow(self.agent_manager.profile.agent_home)
        self._iflow_flow = IFlowAuthCliFlow()
        self._opencode_flow = OpencodeAuthCliFlow()
        self._openai_device_proxy_flow = OpenAIDeviceProxyFlow()
        self._codex_oauth_proxy_flow = CodexOAuthProxyFlow(self.agent_manager.profile.agent_home)
        self._opencode_openai_oauth_proxy_flow = OpencodeOpenAIOAuthProxyFlow(
            self.agent_manager.profile.agent_home
        )
        self._opencode_google_antigravity_oauth_proxy_flow = OpencodeGoogleAntigravityOAuthProxyFlow(
            self.agent_manager.profile.agent_home
        )
        self._driver_registry = AuthDriverRegistry()
        self._auth_log_writer = AuthLogWriter(self._session_root())
        self._session_store = AuthSessionStore()
        self._register_default_driver_matrix()
        self._openai_callback_state_index: Dict[str, str] = {}
        self._openai_callback_state_consumed: set[str] = set()
        self._gemini_callback_state_index: Dict[str, str] = {}
        self._gemini_callback_state_consumed: set[str] = set()
        self._antigravity_callback_state_index: Dict[str, str] = {}
        self._antigravity_callback_state_consumed: set[str] = set()
        self._iflow_callback_state_index: Dict[str, str] = {}
        self._iflow_callback_state_consumed: set[str] = set()

    def _enabled(self) -> bool:
        return bool(config.SYSTEM.ENGINE_AUTH_DEVICE_PROXY_ENABLED)

    def _register_default_driver_matrix(self) -> None:
        # oauth_proxy
        self._driver_registry.register(
            transport="oauth_proxy", engine="codex", auth_method=_AUTH_METHOD_CALLBACK
        )
        self._driver_registry.register(
            transport="oauth_proxy", engine="codex", auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL
        )
        self._driver_registry.register(
            transport="oauth_proxy", engine="gemini", auth_method=_AUTH_METHOD_CALLBACK
        )
        self._driver_registry.register(
            transport="oauth_proxy", engine="gemini", auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL
        )
        self._driver_registry.register(
            transport="oauth_proxy", engine="iflow", auth_method=_AUTH_METHOD_CALLBACK
        )
        self._driver_registry.register(
            transport="oauth_proxy", engine="iflow", auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL
        )
        self._driver_registry.register(
            transport="oauth_proxy",
            engine="opencode",
            auth_method=_AUTH_METHOD_CALLBACK,
            provider_id="openai",
        )
        self._driver_registry.register(
            transport="oauth_proxy",
            engine="opencode",
            auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL,
            provider_id="openai",
        )
        self._driver_registry.register(
            transport="oauth_proxy",
            engine="opencode",
            auth_method=_AUTH_METHOD_CALLBACK,
            provider_id="google",
        )
        self._driver_registry.register(
            transport="oauth_proxy",
            engine="opencode",
            auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL,
            provider_id="google",
        )
        # cli_delegate
        self._driver_registry.register(
            transport="cli_delegate", engine="codex", auth_method=_AUTH_METHOD_CALLBACK
        )
        self._driver_registry.register(
            transport="cli_delegate", engine="codex", auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL
        )
        self._driver_registry.register(
            transport="cli_delegate",
            engine="opencode",
            auth_method=_AUTH_METHOD_CALLBACK,
            provider_id="openai",
        )
        self._driver_registry.register(
            transport="cli_delegate",
            engine="opencode",
            auth_method=_AUTH_METHOD_CALLBACK,
        )
        self._driver_registry.register(
            transport="cli_delegate",
            engine="opencode",
            auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL,
            provider_id="openai",
        )
        self._driver_registry.register(
            transport="cli_delegate",
            engine="gemini",
            auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL,
        )
        self._driver_registry.register(
            transport="cli_delegate",
            engine="iflow",
            auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL,
        )
        self._driver_registry.register(
            transport="cli_delegate", engine="opencode", auth_method=_AUTH_METHOD_AUTH_CODE_OR_URL, provider_id="google"
        )
        self._driver_registry.register(
            transport="cli_delegate", engine="opencode", auth_method=_AUTH_METHOD_API_KEY
        )

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

    def _openai_callback_url(self, callback_base_url: str | None = None) -> str:
        configured = str(config.SYSTEM.ENGINE_AUTH_OAUTH_CALLBACK_BASE_URL or "").strip()
        if configured:
            if configured.endswith("/auth/callback"):
                return configured.rstrip("/")
            return f"{configured.rstrip('/')}/auth/callback"
        # OpenAI OAuth for Codex/OpenCode is coupled to localhost callback URI.
        # We keep manual code/URL paste as fallback when local callback is unavailable.
        _ = callback_base_url
        return _OPENAI_LOCAL_REDIRECT_URI

    def _antigravity_callback_url(self, callback_base_url: str | None = None) -> str:
        _ = callback_base_url
        return _ANTIGRAVITY_LOCAL_REDIRECT_URI

    def _gemini_callback_url(
        self,
        listener_endpoint: str | None = None,
        callback_base_url: str | None = None,
    ) -> str:
        # Gemini loopback OAuth requires localhost callback URI semantics.
        _ = callback_base_url
        if listener_endpoint:
            return listener_endpoint.strip()
        return _GEMINI_LOCAL_REDIRECT_URI

    def _iflow_callback_url(
        self,
        listener_endpoint: str | None = None,
        callback_base_url: str | None = None,
    ) -> str:
        _ = callback_base_url
        if listener_endpoint:
            return listener_endpoint.strip()
        return _IFLOW_LOCAL_REDIRECT_URI

    def _start_openai_local_callback_listener(self) -> bool:
        from .openai_local_callback_server import openai_local_callback_server

        openai_local_callback_server.set_callback_handler(self.complete_openai_callback)
        return bool(openai_local_callback_server.start())

    def _stop_openai_local_callback_listener(self) -> None:
        from .openai_local_callback_server import openai_local_callback_server

        openai_local_callback_server.stop()

    def _start_gemini_local_callback_listener(self) -> str | None:
        from .gemini_local_callback_server import gemini_local_callback_server

        gemini_local_callback_server.set_callback_handler(self.complete_gemini_callback)
        if not gemini_local_callback_server.start():
            return None
        return gemini_local_callback_server.endpoint

    def _stop_gemini_local_callback_listener(self) -> None:
        from .gemini_local_callback_server import gemini_local_callback_server

        gemini_local_callback_server.stop()

    def _start_iflow_local_callback_listener(self) -> str | None:
        from .iflow_local_callback_server import iflow_local_callback_server

        iflow_local_callback_server.set_callback_handler(self.complete_iflow_callback)
        if not iflow_local_callback_server.start():
            return None
        return iflow_local_callback_server.endpoint

    def _stop_iflow_local_callback_listener(self) -> None:
        from .iflow_local_callback_server import iflow_local_callback_server

        iflow_local_callback_server.stop()

    def _start_antigravity_local_callback_listener(self) -> bool:
        from .antigravity_local_callback_server import antigravity_local_callback_server

        antigravity_local_callback_server.set_callback_handler(self.complete_google_antigravity_callback)
        return bool(antigravity_local_callback_server.start())

    def _stop_antigravity_local_callback_listener(self) -> None:
        from .antigravity_local_callback_server import antigravity_local_callback_server

        antigravity_local_callback_server.stop()

    def _register_openai_state(self, session_id: str, state: str) -> None:
        self._openai_callback_state_index[state] = session_id
        self._openai_callback_state_consumed.discard(state)

    def _resolve_openai_state(self, state: str) -> str | None:
        return self._openai_callback_state_index.get(state)

    def _consume_openai_state(self, state: str) -> None:
        self._openai_callback_state_index.pop(state, None)
        self._openai_callback_state_consumed.add(state)

    def _register_antigravity_state(self, session_id: str, state: str) -> None:
        self._antigravity_callback_state_index[state] = session_id
        self._antigravity_callback_state_consumed.discard(state)

    def _register_gemini_state(self, session_id: str, state: str) -> None:
        self._gemini_callback_state_index[state] = session_id
        self._gemini_callback_state_consumed.discard(state)

    def _register_iflow_state(self, session_id: str, state: str) -> None:
        self._iflow_callback_state_index[state] = session_id
        self._iflow_callback_state_consumed.discard(state)

    def _resolve_antigravity_state(self, state: str) -> str | None:
        return self._antigravity_callback_state_index.get(state)

    def _resolve_gemini_state(self, state: str) -> str | None:
        return self._gemini_callback_state_index.get(state)

    def _resolve_iflow_state(self, state: str) -> str | None:
        return self._iflow_callback_state_index.get(state)

    def _consume_antigravity_state(self, state: str) -> None:
        self._antigravity_callback_state_index.pop(state, None)
        self._antigravity_callback_state_consumed.add(state)

    def _consume_gemini_state(self, state: str) -> None:
        self._gemini_callback_state_index.pop(state, None)
        self._gemini_callback_state_consumed.add(state)

    def _consume_iflow_state(self, state: str) -> None:
        self._iflow_callback_state_index.pop(state, None)
        self._iflow_callback_state_consumed.add(state)

    def _remove_openai_state_for_session(self, session: _AuthSession) -> None:
        runtime = session.driver_state
        state: str | None = None
        if isinstance(runtime, CodexOAuthProxySession):
            state = runtime.state
        elif isinstance(runtime, OpencodeOpenAIOAuthProxySession):
            state = runtime.state
        if not state:
            return
        self._openai_callback_state_index.pop(state, None)

    def _remove_antigravity_state_for_session(self, session: _AuthSession) -> None:
        runtime = session.driver_state
        if not isinstance(runtime, OpencodeGoogleAntigravityOAuthProxySession):
            return
        self._antigravity_callback_state_index.pop(runtime.state, None)

    def _remove_gemini_state_for_session(self, session: _AuthSession) -> None:
        runtime = session.driver_state
        if not isinstance(runtime, GeminiOAuthProxySession):
            return
        self._gemini_callback_state_index.pop(runtime.state, None)

    def _remove_iflow_state_for_session(self, session: _AuthSession) -> None:
        runtime = session.driver_state
        if not isinstance(runtime, IFlowOAuthProxySession):
            return
        self._iflow_callback_state_index.pop(runtime.state, None)

    def _inject_trust_for_session(self, engine: str, session_dir: Path) -> tuple[str, Path]:
        if engine in {"codex", "gemini"}:
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
        self._rollback_google_antigravity_if_needed(session)
        self._remove_openai_state_for_session(session)
        self._remove_gemini_state_for_session(session)
        self._remove_iflow_state_for_session(session)
        self._remove_antigravity_state_for_session(session)
        if session.transport == _DEFAULT_TRANSPORT and session.driver in {
            "codex_oauth_proxy",
            "opencode_openai_oauth_proxy",
        }:
            self._stop_openai_local_callback_listener()
        if session.transport == _DEFAULT_TRANSPORT and session.driver in {
            "gemini_oauth_proxy",
        }:
            self._stop_gemini_local_callback_listener()
        if session.transport == _DEFAULT_TRANSPORT and session.driver in {
            "iflow_oauth_proxy",
        }:
            self._stop_iflow_local_callback_listener()
        if session.transport == _DEFAULT_TRANSPORT and session.driver in {
            "opencode_google_antigravity_oauth_proxy",
        }:
            self._stop_antigravity_local_callback_listener()
        if self._active_session_id == session.session_id:
            self._active_session_id = None
        self._session_store.clear_active(session.transport, session.session_id)
        self.interaction_gate.release("auth_flow", session.session_id)
        self._cleanup_trust_for_session(session)

    def _rollback_google_antigravity_if_needed(self, session: _AuthSession) -> None:
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
            auth_store = self._build_opencode_auth_store()
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

    def _submit_codex_input(self, session: _AuthSession, value: str) -> None:
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

    def _refresh_session_locked(self, session: _AuthSession) -> None:
        previous_status = session.status
        if session.driver == "codex_oauth_proxy":
            self._refresh_codex_oauth_proxy_session_locked(session)
            if session.status != previous_status:
                self._append_session_event(
                    session,
                    "state_changed",
                    {"from": previous_status, "to": session.status},
                )
            return
        if session.driver == "codex_device_oauth_proxy":
            self._refresh_codex_device_oauth_proxy_session_locked(session)
            if session.status != previous_status:
                self._append_session_event(
                    session,
                    "state_changed",
                    {"from": previous_status, "to": session.status},
                )
            return
        if session.driver == "opencode_openai_oauth_proxy":
            self._refresh_opencode_openai_oauth_proxy_session_locked(session)
            if session.status != previous_status:
                self._append_session_event(
                    session,
                    "state_changed",
                    {"from": previous_status, "to": session.status},
                )
            return
        if session.driver == "opencode_google_antigravity_oauth_proxy":
            self._refresh_opencode_google_antigravity_oauth_proxy_session_locked(session)
            if session.status != previous_status:
                self._append_session_event(
                    session,
                    "state_changed",
                    {"from": previous_status, "to": session.status},
                )
            return
        if session.driver == "opencode_openai_device_oauth_proxy":
            self._refresh_opencode_openai_device_oauth_proxy_session_locked(session)
            if session.status != previous_status:
                self._append_session_event(
                    session,
                    "state_changed",
                    {"from": previous_status, "to": session.status},
                )
            return
        if session.driver == "gemini_oauth_proxy":
            self._refresh_gemini_oauth_proxy_session_locked(session)
            if session.status != previous_status:
                self._append_session_event(
                    session,
                    "state_changed",
                    {"from": previous_status, "to": session.status},
                )
            return
        if session.driver == "iflow_oauth_proxy":
            self._refresh_iflow_oauth_proxy_session_locked(session)
            if session.status != previous_status:
                self._append_session_event(
                    session,
                    "state_changed",
                    {"from": previous_status, "to": session.status},
                )
            return
        if session.driver == "gemini":
            self._refresh_gemini_session_locked(session)
            if session.status != previous_status:
                self._append_session_event(
                    session,
                    "state_changed",
                    {"from": previous_status, "to": session.status},
                )
            return
        if session.driver == "iflow":
            self._refresh_iflow_session_locked(session)
            if session.status != previous_status:
                self._append_session_event(
                    session,
                    "state_changed",
                    {"from": previous_status, "to": session.status},
                )
            return
        if session.driver == "opencode":
            self._refresh_opencode_session_locked(session)
            if session.status != previous_status:
                self._append_session_event(
                    session,
                    "state_changed",
                    {"from": previous_status, "to": session.status},
                )
            return

        now = _utc_now()
        session.updated_at = now

        if session.status in _TERMINAL_STATUSES:
            session.auth_ready = self._collect_auth_ready(session.engine)
            if session.status != previous_status:
                self._append_session_event(
                    session,
                    "state_changed",
                    {"from": previous_status, "to": session.status},
                )
            return

        if now > session.expires_at:
            self._terminate_process(session)
            session.status = "expired"
            session.error = "Auth session expired"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            if session.status != previous_status:
                self._append_session_event(
                    session,
                    "state_changed",
                    {"from": previous_status, "to": session.status},
                )
            return

        if session.output_path is None or session.process is None:
            session.status = "failed"
            session.error = f"{session.engine} auth session is missing process context"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return

        text = self._read_output_text(session.output_path)
        auth_url = self._extract_auth_url(text)
        if auth_url:
            session.auth_url = auth_url
        user_code = self._extract_user_code(text)
        if user_code:
            session.user_code = user_code

        rc = session.process.poll()
        if rc is None:
            if session.status == "starting":
                session.status = "waiting_user"
            session.auth_ready = self._collect_auth_ready(session.engine)
            return

        session.exit_code = rc
        session.auth_ready = self._collect_auth_ready(session.engine)
        if session.status == "canceled":
            pass
        elif session.auth_ready:
            session.status = "succeeded"
            session.error = None
            self._mark_auto_callback_success(session)
        else:
            session.status = "failed"
            session.error = self._build_error_summary(
                text,
                fallback=f"{session.engine} login exited with code {rc}",
            )
        self._finalize_active_session(session)

    def _refresh_gemini_session_locked(self, session: _AuthSession) -> None:
        runtime = session.driver_state
        if runtime is None or not isinstance(runtime, GeminiAuthCliSession):
            session.status = "failed"
            session.error = "Gemini auth session driver is missing"
            session.auth_ready = False
            if self._active_session_id == session.session_id:
                self._active_session_id = None
            self.interaction_gate.release("auth_flow", session.session_id)
            return

        self._gemini_flow.refresh(runtime)
        session.updated_at = runtime.updated_at
        session.status = runtime.status
        session.auth_url = runtime.auth_url
        session.user_code = None
        session.error = runtime.error
        session.exit_code = runtime.exit_code
        session.auth_ready = runtime.status == "succeeded"

        if runtime.status in _TERMINAL_STATUSES:
            self._finalize_active_session(session)

    def _refresh_gemini_oauth_proxy_session_locked(self, session: _AuthSession) -> None:
        runtime = session.driver_state
        if runtime is None or not isinstance(runtime, GeminiOAuthProxySession):
            session.status = "failed"
            session.error = "Gemini OAuth proxy session driver is missing"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return
        now = _utc_now()
        session.updated_at = now
        runtime.updated_at = now
        if session.status in _TERMINAL_STATUSES:
            session.auth_ready = self._collect_auth_ready(session.engine)
            return
        if now > session.expires_at:
            session.status = "expired"
            session.error = "Auth session expired"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return
        if session.status == "starting":
            session.status = "waiting_user"
        session.auth_ready = self._collect_auth_ready(session.engine)

    def _refresh_iflow_oauth_proxy_session_locked(self, session: _AuthSession) -> None:
        runtime = session.driver_state
        if runtime is None or not isinstance(runtime, IFlowOAuthProxySession):
            session.status = "failed"
            session.error = "iFlow OAuth proxy session driver is missing"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return
        now = _utc_now()
        session.updated_at = now
        runtime.updated_at = now
        if session.status in _TERMINAL_STATUSES:
            session.auth_ready = self._collect_auth_ready(session.engine)
            return
        if now > session.expires_at:
            session.status = "expired"
            session.error = "Auth session expired"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return
        if session.status == "starting":
            session.status = "waiting_user"
        session.auth_ready = self._collect_auth_ready(session.engine)

    def _refresh_opencode_session_locked(self, session: _AuthSession) -> None:
        runtime = session.driver_state
        now = _utc_now()
        session.updated_at = now

        if session.status in _TERMINAL_STATUSES:
            session.auth_ready = self._collect_auth_ready(session.engine)
            return

        if now > session.expires_at:
            self._terminate_process(session)
            session.status = "expired"
            session.error = "Auth session expired"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return

        if runtime is None:
            # API key mode waits user input without subprocess.
            session.auth_ready = self._collect_auth_ready(session.engine)
            return

        if not isinstance(runtime, OpencodeAuthCliSession):
            session.status = "failed"
            session.error = "OpenCode auth session driver is missing"
            session.auth_ready = False
            self._finalize_active_session(session)
            return

        self._opencode_flow.refresh(runtime)
        session.updated_at = runtime.updated_at
        session.status = runtime.status
        session.auth_url = runtime.auth_url
        session.user_code = runtime.user_code
        session.error = runtime.error
        session.exit_code = runtime.exit_code
        session.auth_ready = self._collect_auth_ready(session.engine)
        if session.status == "failed" and session.exit_code == 0 and session.auth_ready:
            session.status = "succeeded"
            session.error = None
            self._mark_auto_callback_success(session)

        if runtime.status in _TERMINAL_STATUSES:
            if runtime.status == "succeeded":
                session.auth_ready = True
                self._mark_auto_callback_success(session)
            self._finalize_active_session(session)

    def _refresh_iflow_session_locked(self, session: _AuthSession) -> None:
        runtime = session.driver_state
        if runtime is None or not isinstance(runtime, IFlowAuthCliSession):
            session.status = "failed"
            session.error = "iFlow auth session driver is missing"
            session.auth_ready = False
            if self._active_session_id == session.session_id:
                self._active_session_id = None
            self.interaction_gate.release("auth_flow", session.session_id)
            return

        self._iflow_flow.refresh(runtime)
        session.updated_at = runtime.updated_at
        session.status = runtime.status
        session.auth_url = runtime.auth_url
        session.user_code = None
        session.error = runtime.error
        session.exit_code = runtime.exit_code
        session.auth_ready = runtime.status == "succeeded"

        if runtime.status in _TERMINAL_STATUSES:
            self._finalize_active_session(session)

    def _refresh_codex_oauth_proxy_session_locked(self, session: _AuthSession) -> None:
        runtime = session.driver_state
        if runtime is None or not isinstance(runtime, CodexOAuthProxySession):
            session.status = "failed"
            session.error = "Codex OAuth proxy session driver is missing"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return
        now = _utc_now()
        session.updated_at = now
        runtime.updated_at = now
        if session.status in _TERMINAL_STATUSES:
            session.auth_ready = self._collect_auth_ready(session.engine)
            return
        if now > session.expires_at:
            session.status = "expired"
            session.error = "Auth session expired"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return
        if session.status == "starting":
            session.status = "waiting_user"
        session.auth_ready = self._collect_auth_ready(session.engine)

    def _refresh_opencode_openai_oauth_proxy_session_locked(self, session: _AuthSession) -> None:
        runtime = session.driver_state
        if runtime is None or not isinstance(runtime, OpencodeOpenAIOAuthProxySession):
            session.status = "failed"
            session.error = "OpenCode OpenAI OAuth proxy session driver is missing"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return
        now = _utc_now()
        session.updated_at = now
        runtime.updated_at = now
        if session.status in _TERMINAL_STATUSES:
            session.auth_ready = self._collect_auth_ready(session.engine)
            return
        if now > session.expires_at:
            session.status = "expired"
            session.error = "Auth session expired"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return
        if session.status == "starting":
            session.status = "waiting_user"
        session.auth_ready = self._collect_auth_ready(session.engine)

    def _refresh_opencode_google_antigravity_oauth_proxy_session_locked(self, session: _AuthSession) -> None:
        runtime = session.driver_state
        if runtime is None or not isinstance(runtime, OpencodeGoogleAntigravityOAuthProxySession):
            session.status = "failed"
            session.error = "OpenCode Google Antigravity OAuth proxy session driver is missing"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return
        now = _utc_now()
        session.updated_at = now
        runtime.updated_at = now
        if session.status in _TERMINAL_STATUSES:
            session.auth_ready = self._collect_auth_ready(session.engine)
            return
        if now > session.expires_at:
            session.status = "expired"
            session.error = "Auth session expired"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return
        if session.status == "starting":
            session.status = "waiting_user"
        session.auth_ready = self._collect_auth_ready(session.engine)

    def _refresh_codex_device_oauth_proxy_session_locked(self, session: _AuthSession) -> None:
        runtime = session.driver_state
        if runtime is None or not isinstance(runtime, OpenAIDeviceProxySession):
            session.status = "failed"
            session.error = "Codex device auth session driver is missing"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return

        now = _utc_now()
        session.updated_at = now
        runtime.updated_at = now
        session.auth_url = runtime.verification_url
        session.user_code = runtime.user_code
        if session.status in _TERMINAL_STATUSES:
            session.auth_ready = self._collect_auth_ready(session.engine)
            return
        if now > session.expires_at:
            session.status = "expired"
            session.error = "Auth session expired"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return
        if session.status == "starting":
            session.status = "waiting_user"
        try:
            token_set = self._openai_device_proxy_flow.poll_once(runtime, now=now)
            if token_set is None:
                session.auth_ready = self._collect_auth_ready(session.engine)
                return
            self._codex_oauth_proxy_flow.complete_with_tokens(token_set)
            session.status = "succeeded"
            session.error = None
            session.auth_ready = self._collect_auth_ready("codex")
            self._mark_auto_callback_success(session)
            self._finalize_active_session(session)
        except Exception as exc:
            session.status = "failed"
            session.error = f"OpenAI device auth failed: {exc}"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)

    def _refresh_opencode_openai_device_oauth_proxy_session_locked(self, session: _AuthSession) -> None:
        runtime = session.driver_state
        if runtime is None or not isinstance(runtime, OpenAIDeviceProxySession):
            session.status = "failed"
            session.error = "OpenCode OpenAI device auth session driver is missing"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return

        now = _utc_now()
        session.updated_at = now
        runtime.updated_at = now
        session.auth_url = runtime.verification_url
        session.user_code = runtime.user_code
        if session.status in _TERMINAL_STATUSES:
            session.auth_ready = self._collect_auth_ready(session.engine)
            return
        if now > session.expires_at:
            session.status = "expired"
            session.error = "Auth session expired"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return
        if session.status == "starting":
            session.status = "waiting_user"
        try:
            token_set = self._openai_device_proxy_flow.poll_once(runtime, now=now)
            if token_set is None:
                session.auth_ready = self._collect_auth_ready(session.engine)
                return
            self._opencode_openai_oauth_proxy_flow.complete_with_tokens(token_set)
            session.status = "succeeded"
            session.error = None
            session.auth_ready = self._collect_auth_ready("opencode")
            self._mark_auto_callback_success(session)
            self._finalize_active_session(session)
        except Exception as exc:
            session.status = "failed"
            session.error = f"OpenAI device auth failed: {exc}"
            session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)

    def _terminate_process(self, session: _AuthSession) -> None:
        if session.driver == "gemini":
            runtime = session.driver_state
            if runtime is not None and isinstance(runtime, GeminiAuthCliSession):
                self._gemini_flow.cancel(runtime)
            return
        if session.driver == "iflow":
            runtime = session.driver_state
            if runtime is not None and isinstance(runtime, IFlowAuthCliSession):
                self._iflow_flow.cancel(runtime)
            return
        if session.driver == "opencode":
            runtime = session.driver_state
            if runtime is not None and isinstance(runtime, OpencodeAuthCliSession):
                self._opencode_flow.cancel(runtime)
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

        normalized_engine = engine.strip().lower()
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
        provider: OpencodeAuthProvider | None = None
        effective_auth_method: str
        if normalized_engine == "codex":
            if normalized_auth_method is None:
                effective_auth_method = _AUTH_METHOD_CALLBACK
            elif normalized_auth_method in {_AUTH_METHOD_CALLBACK, _AUTH_METHOD_AUTH_CODE_OR_URL}:
                effective_auth_method = normalized_auth_method
            else:
                raise ValueError(
                    "Unsupported auth_method for codex: use callback or auth_code_or_url"
                )
            normalized_method = "auth"
        elif normalized_engine == "gemini":
            if normalized_transport == _DEFAULT_TRANSPORT:
                if normalized_auth_method is None:
                    effective_auth_method = _AUTH_METHOD_CALLBACK
                elif normalized_auth_method in {_AUTH_METHOD_CALLBACK, _AUTH_METHOD_AUTH_CODE_OR_URL}:
                    effective_auth_method = normalized_auth_method
                else:
                    raise ValueError(
                        "Unsupported auth_method for gemini oauth_proxy: use callback or auth_code_or_url"
                    )
                normalized_method = "auth"
            elif normalized_transport == "cli_delegate":
                if normalized_auth_method is None:
                    effective_auth_method = _AUTH_METHOD_AUTH_CODE_OR_URL
                elif normalized_auth_method == _AUTH_METHOD_AUTH_CODE_OR_URL:
                    effective_auth_method = normalized_auth_method
                else:
                    raise ValueError(
                        "Unsupported auth_method for gemini cli_delegate: only auth_code_or_url is allowed"
                    )
                normalized_method = "auth"
            else:
                raise ValueError(
                    "Unsupported transport combination: gemini only supports oauth_proxy|cli_delegate"
                )
        elif normalized_engine == "iflow":
            if normalized_transport == _DEFAULT_TRANSPORT:
                if normalized_auth_method is None:
                    effective_auth_method = _AUTH_METHOD_CALLBACK
                elif normalized_auth_method in {_AUTH_METHOD_CALLBACK, _AUTH_METHOD_AUTH_CODE_OR_URL}:
                    effective_auth_method = normalized_auth_method
                else:
                    raise ValueError(
                        "Unsupported auth_method for iflow oauth_proxy: use callback or auth_code_or_url"
                    )
            elif normalized_transport == "cli_delegate":
                if normalized_auth_method is None:
                    effective_auth_method = _AUTH_METHOD_AUTH_CODE_OR_URL
                elif normalized_auth_method == _AUTH_METHOD_AUTH_CODE_OR_URL:
                    effective_auth_method = normalized_auth_method
                else:
                    raise ValueError(
                        "Unsupported auth_method for iflow cli_delegate: only auth_code_or_url is allowed"
                    )
            else:
                raise ValueError(
                    "Unsupported transport combination: iflow only supports oauth_proxy|cli_delegate"
                )
            normalized_method = "auth"
        elif normalized_engine == "opencode":
            if not normalized_provider:
                raise ValueError("provider_id is required for opencode auth sessions")
            provider = opencode_auth_provider_registry.get(normalized_provider)
            if normalized_transport == _DEFAULT_TRANSPORT and provider.provider_id not in {"openai", "google"}:
                raise ValueError(
                    "Unsupported transport combination: opencode oauth_proxy only supports provider_id=openai|google"
                )
            if provider.auth_mode == "api_key":
                if normalized_auth_method and normalized_auth_method != _AUTH_METHOD_API_KEY:
                    raise ValueError(
                        "Unsupported auth_method for OpenCode API key provider: use api_key"
                    )
                effective_auth_method = _AUTH_METHOD_API_KEY
                normalized_method = "auth"
            elif provider.provider_id == "openai":
                if normalized_auth_method is None:
                    effective_auth_method = _AUTH_METHOD_CALLBACK
                elif normalized_auth_method in {_AUTH_METHOD_CALLBACK, _AUTH_METHOD_AUTH_CODE_OR_URL}:
                    effective_auth_method = normalized_auth_method
                else:
                    raise ValueError(
                        "Unsupported auth_method for OpenCode OpenAI: use callback or auth_code_or_url"
                    )
                normalized_method = "auth"
            elif provider.provider_id == "google" and normalized_transport == _DEFAULT_TRANSPORT:
                if normalized_auth_method is None:
                    effective_auth_method = _AUTH_METHOD_CALLBACK
                elif normalized_auth_method in {_AUTH_METHOD_CALLBACK, _AUTH_METHOD_AUTH_CODE_OR_URL}:
                    effective_auth_method = normalized_auth_method
                else:
                    raise ValueError(
                        "Unsupported auth_method for OpenCode Google oauth_proxy: use callback or auth_code_or_url"
                    )
                normalized_method = "auth"
            else:
                if provider.provider_id == "google":
                    if normalized_auth_method is None:
                        effective_auth_method = _AUTH_METHOD_AUTH_CODE_OR_URL
                    elif normalized_auth_method == _AUTH_METHOD_AUTH_CODE_OR_URL:
                        effective_auth_method = normalized_auth_method
                    else:
                        raise ValueError(
                            "Unsupported auth_method for OpenCode Google cli_delegate: only auth_code_or_url is allowed"
                        )
                else:
                    if normalized_auth_method is None:
                        effective_auth_method = _AUTH_METHOD_CALLBACK
                    elif normalized_auth_method in {_AUTH_METHOD_CALLBACK, _AUTH_METHOD_AUTH_CODE_OR_URL}:
                        effective_auth_method = normalized_auth_method
                    else:
                        raise ValueError(
                            "Unsupported auth_method for OpenCode OAuth provider: use callback or auth_code_or_url"
                        )
                normalized_method = "auth"
        else:
            raise ValueError("Unsupported engine for auth proxy")

        registry_provider_id: str | None = None
        if normalized_engine == "opencode":
            if provider is not None and provider.auth_mode == "api_key":
                registry_provider_id = None
            elif provider is not None:
                registry_provider_id = provider.provider_id
        if not self._driver_registry.supports(
            transport=normalized_transport,
            engine=normalized_engine,
            auth_method=effective_auth_method,
            provider_id=registry_provider_id,
        ):
            raise ValueError(
                "Unsupported auth combination: "
                f"transport={normalized_transport}, engine={normalized_engine}, "
                f"auth_method={effective_auth_method}, provider_id={registry_provider_id or '-'}"
            )

        requires_command = True
        if normalized_engine == "codex" and normalized_transport == _DEFAULT_TRANSPORT:
            requires_command = False
        if normalized_engine == "gemini" and normalized_transport == _DEFAULT_TRANSPORT:
            requires_command = False
        if normalized_engine == "iflow" and normalized_transport == _DEFAULT_TRANSPORT:
            requires_command = False
        if normalized_engine == "opencode":
            if (
                normalized_transport == _DEFAULT_TRANSPORT
                and provider is not None
                and provider.provider_id in {"openai", "google"}
            ):
                requires_command = False
            if provider is not None and provider.auth_mode == "api_key":
                requires_command = False
        command = self.agent_manager.resolve_engine_command(normalized_engine) if requires_command else None
        if requires_command and command is None:
            raise RuntimeError(f"{normalized_engine} CLI not found")

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

            log_paths = self._auth_log_writer.init_paths(
                transport=normalized_transport,
                session_id=session_id,
            )
            session_dir = log_paths.root
            trust_engine: str | None = None
            trust_path: Path | None = None
            output_path = log_paths.primary_log_path

            env = self.agent_manager.profile.build_subprocess_env(os.environ.copy())
            env.setdefault("TERM", "xterm-256color")
            now = _utc_now()
            expires_at = now + timedelta(seconds=self._ttl_seconds())
            openai_listener_started = False
            gemini_listener_started = False
            gemini_listener_endpoint: str | None = None
            iflow_listener_started = False
            iflow_listener_endpoint: str | None = None
            antigravity_listener_started = False

            try:
                trust_engine, trust_path = self._inject_trust_for_session(
                    normalized_engine,
                    session_dir,
                )
                if normalized_engine == "codex":
                    if normalized_transport == _DEFAULT_TRANSPORT:
                        if effective_auth_method == _AUTH_METHOD_CALLBACK:
                            openai_listener_started = self._start_openai_local_callback_listener()
                            if not openai_listener_started:
                                raise ValueError(
                                    "Codex callback mode requires local callback listener on localhost:1455"
                                )
                            codex_proxy_runtime = self._codex_oauth_proxy_flow.start_session(
                                session_id=session_id,
                                callback_url=self._openai_callback_url(callback_base_url),
                                now=now,
                            )
                            self._register_openai_state(session_id, codex_proxy_runtime.state)
                            session = _AuthSession(
                                session_id=session_id,
                                engine=normalized_engine,
                                method=normalized_method,
                                auth_method=effective_auth_method,
                                transport=normalized_transport,
                                provider_id=None,
                                provider_name=None,
                                created_at=now,
                                updated_at=now,
                                expires_at=expires_at,
                                status="starting",
                                input_kind="text",
                                output_path=output_path,
                                process=None,
                                auth_url=codex_proxy_runtime.auth_url,
                                driver="codex_oauth_proxy",
                                driver_state=codex_proxy_runtime,
                                execution_mode="protocol_proxy",
                                trust_engine=trust_engine,
                                trust_path=trust_path,
                                audit={
                                    "manual_fallback_used": False,
                                    "auto_callback_success": False,
                                    "local_callback_listener_started": openai_listener_started,
                                    "auto_callback_listener_started": openai_listener_started,
                                },
                            )
                        else:
                            try:
                                codex_device_runtime = self._openai_device_proxy_flow.start_session(
                                    session_id=session_id,
                                    now=now,
                                    user_agent=_OPENAI_DEVICE_USER_AGENT_CODEX,
                                )
                            except Exception as exc:
                                raise self._build_openai_device_start_error(exc) from exc
                            session = _AuthSession(
                                session_id=session_id,
                                engine=normalized_engine,
                                method=normalized_method,
                                auth_method=effective_auth_method,
                                transport=normalized_transport,
                                provider_id=None,
                                provider_name=None,
                                created_at=now,
                                updated_at=now,
                                expires_at=expires_at,
                                status="starting",
                                input_kind=None,
                                output_path=output_path,
                                process=None,
                                auth_url=codex_device_runtime.verification_url,
                                user_code=codex_device_runtime.user_code,
                                driver="codex_device_oauth_proxy",
                                driver_state=codex_device_runtime,
                                execution_mode="protocol_proxy",
                                trust_engine=trust_engine,
                                trust_path=trust_path,
                                audit={
                                    "manual_fallback_used": False,
                                    "auto_callback_success": False,
                                    "local_callback_listener_started": False,
                                },
                            )
                    else:
                        if command is None:
                            raise RuntimeError("codex CLI not found")
                        command_args = [str(command), "login"]
                        if effective_auth_method == _AUTH_METHOD_AUTH_CODE_OR_URL:
                            command_args.append("--device-auth")
                        with output_path.open("w", encoding="utf-8") as stream:
                            process = subprocess.Popen(
                                command_args,
                                cwd=str(session_dir),
                                env=env,
                                stdin=subprocess.PIPE,
                                stdout=stream,
                                stderr=subprocess.STDOUT,
                                text=True,
                                start_new_session=True,
                            )
                        session = _AuthSession(
                            session_id=session_id,
                            engine=normalized_engine,
                            method=normalized_method,
                            auth_method=effective_auth_method,
                            transport=normalized_transport,
                            provider_id=None,
                            provider_name=None,
                            created_at=now,
                            updated_at=now,
                            expires_at=expires_at,
                            status="starting",
                            input_kind=(
                                "text" if effective_auth_method == _AUTH_METHOD_CALLBACK else None
                            ),
                            output_path=output_path,
                            process=process,
                            driver="codex",
                            execution_mode="cli_delegate",
                            trust_engine=trust_engine,
                            trust_path=trust_path,
                        )
                elif normalized_engine == "gemini":
                    if normalized_transport == _DEFAULT_TRANSPORT:
                        if effective_auth_method == _AUTH_METHOD_CALLBACK:
                            gemini_listener_endpoint = self._start_gemini_local_callback_listener()
                            gemini_listener_started = bool(gemini_listener_endpoint)
                            if not gemini_listener_started:
                                raise ValueError(
                                    "Gemini callback mode requires local callback listener on localhost:51122"
                                )
                            callback_url = self._gemini_callback_url(
                                listener_endpoint=gemini_listener_endpoint,
                                callback_base_url=callback_base_url,
                            )
                            input_kind = "text"
                        else:
                            callback_url = _GEMINI_MANUAL_REDIRECT_URI
                            input_kind = "text"
                        gemini_runtime = self._gemini_oauth_proxy_flow.start_session(
                            session_id=session_id,
                            callback_url=callback_url,
                            now=now,
                        )
                        self._register_gemini_state(session_id, gemini_runtime.state)
                        session = _AuthSession(
                            session_id=session_id,
                            engine=normalized_engine,
                            method=normalized_method,
                            auth_method=effective_auth_method,
                            transport=normalized_transport,
                            provider_id=None,
                            provider_name=None,
                            created_at=now,
                            updated_at=now,
                            expires_at=expires_at,
                            status="starting",
                            input_kind=input_kind,
                            output_path=output_path,
                            process=None,
                            auth_url=gemini_runtime.auth_url,
                            driver="gemini_oauth_proxy",
                            driver_state=gemini_runtime,
                            execution_mode="protocol_proxy",
                            trust_engine=trust_engine,
                            trust_path=trust_path,
                            audit={
                                "manual_fallback_used": False,
                                "auto_callback_success": False,
                                "local_callback_listener_started": gemini_listener_started,
                                "auto_callback_listener_started": gemini_listener_started,
                            },
                        )
                    else:
                        self._prepare_gemini_auth_workspace(session_dir)
                        runtime = self._gemini_flow.start_session(
                            session_id=session_id,
                            command_path=command,
                            cwd=session_dir,
                            env=env,
                            output_path=output_path,
                            expires_at=expires_at,
                        )
                        session = _AuthSession(
                            session_id=session_id,
                            engine=normalized_engine,
                            method=normalized_method,
                            auth_method=effective_auth_method,
                            transport=normalized_transport,
                            provider_id=None,
                            provider_name=None,
                            created_at=now,
                            updated_at=now,
                            expires_at=expires_at,
                            status="starting",
                            input_kind="code",
                            output_path=output_path,
                            process=runtime.process,
                            driver="gemini",
                            driver_state=runtime,
                            trust_engine=trust_engine,
                            trust_path=trust_path,
                        )
                elif normalized_engine == "iflow":
                    if normalized_transport == _DEFAULT_TRANSPORT:
                        if effective_auth_method == _AUTH_METHOD_CALLBACK:
                            iflow_listener_endpoint = self._start_iflow_local_callback_listener()
                            iflow_listener_started = bool(iflow_listener_endpoint)
                            callback_url = self._iflow_callback_url(
                                listener_endpoint=iflow_listener_endpoint,
                                callback_base_url=callback_base_url,
                            )
                        else:
                            callback_url = _IFLOW_MANUAL_REDIRECT_URI
                        iflow_proxy_runtime = self._iflow_oauth_proxy_flow.start_session(
                            session_id=session_id,
                            callback_url=callback_url,
                            auth_method=effective_auth_method,
                            now=now,
                        )
                        self._register_iflow_state(session_id, iflow_proxy_runtime.state)
                        session = _AuthSession(
                            session_id=session_id,
                            engine=normalized_engine,
                            method=normalized_method,
                            auth_method=effective_auth_method,
                            transport=normalized_transport,
                            provider_id=None,
                            provider_name=None,
                            created_at=now,
                            updated_at=now,
                            expires_at=expires_at,
                            status="starting",
                            input_kind="text",
                            output_path=output_path,
                            process=None,
                            auth_url=iflow_proxy_runtime.auth_url,
                            driver="iflow_oauth_proxy",
                            driver_state=iflow_proxy_runtime,
                            execution_mode="protocol_proxy",
                            trust_engine=trust_engine,
                            trust_path=trust_path,
                            audit={
                                "manual_fallback_used": False,
                                "auto_callback_success": False,
                                "local_callback_listener_started": iflow_listener_started,
                                "auto_callback_listener_started": iflow_listener_started,
                            },
                        )
                    else:
                        runtime = self._iflow_flow.start_session(
                            session_id=session_id,
                            command_path=command,
                            cwd=session_dir,
                            env=env,
                            output_path=output_path,
                            expires_at=expires_at,
                        )
                        session = _AuthSession(
                            session_id=session_id,
                            engine=normalized_engine,
                            method=normalized_method,
                            auth_method=effective_auth_method,
                            transport=normalized_transport,
                            provider_id=None,
                            provider_name=None,
                            created_at=now,
                            updated_at=now,
                            expires_at=expires_at,
                            status="starting",
                            input_kind="code",
                            output_path=output_path,
                            process=runtime.process,
                            driver="iflow",
                            driver_state=runtime,
                            trust_engine=trust_engine,
                            trust_path=trust_path,
                        )
                else:
                    assert provider is not None
                    if normalized_transport == _DEFAULT_TRANSPORT and provider.provider_id in {"openai", "google"}:
                        if provider.provider_id == "openai" and effective_auth_method == _AUTH_METHOD_CALLBACK:
                            openai_listener_started = self._start_openai_local_callback_listener()
                            if not openai_listener_started:
                                raise ValueError(
                                    "OpenCode OpenAI callback mode requires local callback listener on localhost:1455"
                                )
                            opencode_proxy_runtime = self._opencode_openai_oauth_proxy_flow.start_session(
                                session_id=session_id,
                                callback_url=self._openai_callback_url(callback_base_url),
                                now=now,
                            )
                            self._register_openai_state(session_id, opencode_proxy_runtime.state)
                            session = _AuthSession(
                                session_id=session_id,
                                engine=normalized_engine,
                                method=normalized_method,
                                auth_method=effective_auth_method,
                                transport=normalized_transport,
                                provider_id=provider.provider_id,
                                provider_name=provider.display_name,
                                created_at=now,
                                updated_at=now,
                                expires_at=expires_at,
                                status="starting",
                                input_kind="text",
                                output_path=output_path,
                                process=None,
                                auth_url=opencode_proxy_runtime.auth_url,
                                driver="opencode_openai_oauth_proxy",
                                driver_state=opencode_proxy_runtime,
                                execution_mode="protocol_proxy",
                                audit={
                                    "manual_fallback_used": False,
                                    "auto_callback_success": False,
                                    "local_callback_listener_started": openai_listener_started,
                                    "auto_callback_listener_started": openai_listener_started,
                                },
                                trust_engine=trust_engine,
                                trust_path=trust_path,
                            )
                        elif provider.provider_id == "openai":
                            try:
                                opencode_device_runtime = self._openai_device_proxy_flow.start_session(
                                    session_id=session_id,
                                    now=now,
                                    user_agent=_OPENAI_DEVICE_USER_AGENT_OPENCODE,
                                )
                            except Exception as exc:
                                raise self._build_openai_device_start_error(exc) from exc
                            session = _AuthSession(
                                session_id=session_id,
                                engine=normalized_engine,
                                method=normalized_method,
                                auth_method=effective_auth_method,
                                transport=normalized_transport,
                                provider_id=provider.provider_id,
                                provider_name=provider.display_name,
                                created_at=now,
                                updated_at=now,
                                expires_at=expires_at,
                                status="starting",
                                input_kind=None,
                                output_path=output_path,
                                process=None,
                                auth_url=opencode_device_runtime.verification_url,
                                user_code=opencode_device_runtime.user_code,
                                driver="opencode_openai_device_oauth_proxy",
                                driver_state=opencode_device_runtime,
                                execution_mode="protocol_proxy",
                                audit={
                                    "manual_fallback_used": False,
                                    "auto_callback_success": False,
                                    "local_callback_listener_started": False,
                                },
                                trust_engine=trust_engine,
                                trust_path=trust_path,
                            )
                        else:
                            antigravity_listener_started = False
                            if effective_auth_method == _AUTH_METHOD_CALLBACK:
                                antigravity_listener_started = self._start_antigravity_local_callback_listener()
                                if not antigravity_listener_started:
                                    raise ValueError(
                                        "OpenCode Google callback mode requires local callback listener on localhost:51121"
                                    )
                            antigravity_runtime = self._opencode_google_antigravity_oauth_proxy_flow.start_session(
                                session_id=session_id,
                                auth_method=effective_auth_method,
                                now=now,
                            )
                            self._register_antigravity_state(session_id, antigravity_runtime.state)
                            session = _AuthSession(
                                session_id=session_id,
                                engine=normalized_engine,
                                method=normalized_method,
                                auth_method=effective_auth_method,
                                transport=normalized_transport,
                                provider_id=provider.provider_id,
                                provider_name=provider.display_name,
                                created_at=now,
                                updated_at=now,
                                expires_at=expires_at,
                                status="starting",
                                input_kind="text",
                                output_path=output_path,
                                process=None,
                                auth_url=antigravity_runtime.auth_url,
                                driver="opencode_google_antigravity_oauth_proxy",
                                driver_state=antigravity_runtime,
                                execution_mode="protocol_proxy",
                                trust_engine=trust_engine,
                                trust_path=trust_path,
                                audit={
                                    "manual_fallback_used": False,
                                    "auto_callback_success": False,
                                    "local_callback_listener_started": antigravity_listener_started,
                                    "auto_callback_listener_started": antigravity_listener_started,
                                },
                            )
                    else:
                        audit: Dict[str, Any] = {}
                        auth_store = self._build_opencode_auth_store()
                        if provider.provider_id == "google":
                            backup_info = auth_store.backup_antigravity_accounts(
                                session_dir / "antigravity-accounts.pre_auth.backup.json"
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
                                        backup_path=(
                                            str(backup_info.get("backup_path"))
                                            if backup_info.get("backup_path")
                                            else None
                                        ),
                                    )
                                    rollback_success = True
                                except Exception as rollback_exc:
                                    rollback_error = str(rollback_exc)
                                session = _AuthSession(
                                    session_id=session_id,
                                    engine=normalized_engine,
                                    method=normalized_method,
                                    auth_method=effective_auth_method,
                                    transport=normalized_transport,
                                    provider_id=provider.provider_id,
                                    provider_name=provider.display_name,
                                    created_at=now,
                                    updated_at=now,
                                    expires_at=expires_at,
                                    status="failed",
                                    input_kind="text",
                                    output_path=output_path,
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
                                    auth_ready=self._collect_auth_ready("opencode"),
                                    execution_mode="cli_delegate",
                                    trust_engine=trust_engine,
                                    trust_path=trust_path,
                                )
                                session.log_root = session_dir
                                session.log_paths = log_paths
                                self._sessions[session_id] = session
                                self._session_store.upsert(
                                    SessionPointer(
                                        session_id=session_id,
                                        transport=normalized_transport,
                                        engine=normalized_engine,
                                        auth_method=effective_auth_method,
                                        provider_id=provider.provider_id,
                                    )
                                )
                                self._append_session_event(
                                    session,
                                    "session_started",
                                    {
                                        "status": session.status,
                                        "engine": session.engine,
                                        "auth_method": session.auth_method,
                                        "provider_id": session.provider_id,
                                    },
                                )
                                self._finalize_active_session(session)
                                return self._to_snapshot(session)

                        if provider.auth_mode == "api_key":
                            session = _AuthSession(
                                session_id=session_id,
                                engine=normalized_engine,
                                method=normalized_method,
                                auth_method=effective_auth_method,
                                transport=normalized_transport,
                                provider_id=provider.provider_id,
                                provider_name=provider.display_name,
                                created_at=now,
                                updated_at=now,
                                expires_at=expires_at,
                                status="waiting_user",
                                input_kind="api_key",
                                output_path=None,
                                process=None,
                                driver="opencode",
                                driver_state=None,
                                execution_mode="cli_delegate",
                                audit=audit or None,
                                trust_engine=trust_engine,
                                trust_path=trust_path,
                            )
                        else:
                            if command is None:
                                raise RuntimeError("opencode CLI not found")
                            opencode_runtime = self._opencode_flow.start_session(
                                session_id=session_id,
                                command_path=command,
                                cwd=session_dir,
                                env=env,
                                output_path=output_path,
                                expires_at=expires_at,
                                provider_id=provider.provider_id,
                                provider_label=provider.menu_label,
                                openai_auth_method=effective_auth_method,
                            )
                            input_kind = "text"
                            if (
                                provider.provider_id == "openai"
                                and effective_auth_method == _AUTH_METHOD_AUTH_CODE_OR_URL
                            ):
                                input_kind = None
                            session = _AuthSession(
                                session_id=session_id,
                                engine=normalized_engine,
                                method=normalized_method,
                                auth_method=effective_auth_method,
                                transport=normalized_transport,
                                provider_id=provider.provider_id,
                                provider_name=provider.display_name,
                                created_at=now,
                                updated_at=now,
                                expires_at=expires_at,
                                status="starting",
                                input_kind=input_kind,
                                output_path=output_path,
                                process=opencode_runtime.process,
                                driver="opencode",
                                driver_state=opencode_runtime,
                                execution_mode="cli_delegate",
                                audit=audit or None,
                                trust_engine=trust_engine,
                                trust_path=trust_path,
                            )
            except Exception:
                if openai_listener_started:
                    self._stop_openai_local_callback_listener()
                if gemini_listener_started:
                    self._stop_gemini_local_callback_listener()
                if iflow_listener_started:
                    self._stop_iflow_local_callback_listener()
                if antigravity_listener_started:
                    self._stop_antigravity_local_callback_listener()
                if trust_engine and trust_path:
                    try:
                        self.trust_manager.remove_run_folder(trust_engine, trust_path)
                    except Exception:
                        pass
                self.interaction_gate.release("auth_flow", session_id)
                raise
            session.log_root = session_dir
            session.log_paths = log_paths
            self._sessions[session_id] = session
            self._session_store.upsert(
                SessionPointer(
                    session_id=session_id,
                    transport=normalized_transport,
                    engine=normalized_engine,
                    auth_method=effective_auth_method,
                    provider_id=(provider.provider_id if provider is not None else None),
                )
            )
            self._append_session_event(
                session,
                "session_started",
                {
                    "status": session.status,
                    "engine": session.engine,
                    "auth_method": session.auth_method,
                    "provider_id": session.provider_id,
                },
            )
            self._active_session_id = session_id
            self._refresh_session_locked(session)
            return self._to_snapshot(session)

    def complete_openai_callback(
        self,
        *,
        state: str,
        code: str | None = None,
        error: str | None = None,
    ) -> Dict[str, Any]:
        normalized_state = state.strip()
        if not normalized_state:
            raise ValueError("OAuth callback state is required")

        with self._lock:
            if normalized_state in self._openai_callback_state_consumed:
                raise ValueError("OAuth callback state has already been consumed")
            session_id = self._resolve_openai_state(normalized_state)
            if session_id is None:
                raise ValueError("OAuth callback state is invalid")
            session = self._sessions.get(session_id)
            if session is None:
                self._consume_openai_state(normalized_state)
                raise ValueError("OAuth callback session not found")

            self._refresh_session_locked(session)
            if session.status in _TERMINAL_STATUSES:
                self._consume_openai_state(normalized_state)
                raise ValueError("OAuth callback session is already finished")

            runtime = session.driver_state
            if not isinstance(runtime, (CodexOAuthProxySession, OpencodeOpenAIOAuthProxySession)):
                self._consume_openai_state(normalized_state)
                raise ValueError("OAuth callback session does not support OpenAI callback")

            self._consume_openai_state(normalized_state)
            self._mark_oauth_callback_received(session)
            session.updated_at = _utc_now()

            if error and error.strip():
                session.status = "failed"
                session.error = f"OAuth callback error: {error.strip()}"
                session.auth_ready = self._collect_auth_ready(session.engine)
                self._finalize_active_session(session)
                return self._to_snapshot(session)

            normalized_code = (code or "").strip()
            if not normalized_code:
                session.status = "failed"
                session.error = "OAuth callback code is missing"
                session.auth_ready = self._collect_auth_ready(session.engine)
                self._finalize_active_session(session)
                return self._to_snapshot(session)

            try:
                if isinstance(runtime, CodexOAuthProxySession):
                    self._codex_oauth_proxy_flow.complete_with_code(runtime, normalized_code)
                    session.auth_ready = self._collect_auth_ready("codex")
                else:
                    self._opencode_openai_oauth_proxy_flow.complete_with_code(runtime, normalized_code)
                    session.auth_ready = self._collect_auth_ready("opencode")
                session.status = "succeeded"
                session.error = None
                self._mark_auto_callback_success(session)
            except Exception as exc:
                session.status = "failed"
                session.error = f"OAuth callback token exchange failed: {exc}"
                session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return self._to_snapshot(session)

    def complete_google_antigravity_callback(
        self,
        *,
        state: str,
        code: str | None = None,
        error: str | None = None,
    ) -> Dict[str, Any]:
        normalized_state = state.strip()
        if not normalized_state:
            raise ValueError("OAuth callback state is required")

        with self._lock:
            if normalized_state in self._antigravity_callback_state_consumed:
                raise ValueError("OAuth callback state has already been consumed")
            session_id = self._resolve_antigravity_state(normalized_state)
            if session_id is None:
                raise ValueError("OAuth callback state is invalid")
            session = self._sessions.get(session_id)
            if session is None:
                self._consume_antigravity_state(normalized_state)
                raise ValueError("OAuth callback session not found")

            self._refresh_session_locked(session)
            if session.status in _TERMINAL_STATUSES:
                self._consume_antigravity_state(normalized_state)
                raise ValueError("OAuth callback session is already finished")

            runtime = session.driver_state
            if not isinstance(runtime, OpencodeGoogleAntigravityOAuthProxySession):
                self._consume_antigravity_state(normalized_state)
                raise ValueError("OAuth callback session does not support Google Antigravity callback")

            self._consume_antigravity_state(normalized_state)
            self._mark_oauth_callback_received(session)
            session.updated_at = _utc_now()

            if error and error.strip():
                session.status = "failed"
                session.error = f"OAuth callback error: {error.strip()}"
                session.auth_ready = self._collect_auth_ready(session.engine)
                self._finalize_active_session(session)
                return self._to_snapshot(session)

            normalized_code = (code or "").strip()
            if not normalized_code:
                session.status = "failed"
                session.error = "OAuth callback code is missing"
                session.auth_ready = self._collect_auth_ready(session.engine)
                self._finalize_active_session(session)
                return self._to_snapshot(session)

            try:
                flow_result = self._opencode_google_antigravity_oauth_proxy_flow.complete_with_code(
                    runtime=runtime,
                    code=normalized_code,
                    state=normalized_state,
                )
                session.status = "succeeded"
                session.error = None
                session.auth_ready = self._collect_auth_ready("opencode")
                self._mark_auto_callback_success(session)
                audit = self._ensure_audit_dict(session)
                audit.update(flow_result)
                audit["callback_mode"] = "auto"
            except Exception as exc:
                session.status = "failed"
                session.error = f"OAuth callback token exchange failed: {exc}"
                session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return self._to_snapshot(session)

    def complete_gemini_callback(
        self,
        *,
        state: str,
        code: str | None = None,
        error: str | None = None,
    ) -> Dict[str, Any]:
        normalized_state = state.strip()
        if not normalized_state:
            raise ValueError("OAuth callback state is required")

        with self._lock:
            if normalized_state in self._gemini_callback_state_consumed:
                raise ValueError("OAuth callback state has already been consumed")
            session_id = self._resolve_gemini_state(normalized_state)
            if session_id is None:
                raise ValueError("OAuth callback state is invalid")
            session = self._sessions.get(session_id)
            if session is None:
                self._consume_gemini_state(normalized_state)
                raise ValueError("OAuth callback session not found")

            self._refresh_session_locked(session)
            if session.status in _TERMINAL_STATUSES:
                self._consume_gemini_state(normalized_state)
                raise ValueError("OAuth callback session is already finished")

            runtime = session.driver_state
            if not isinstance(runtime, GeminiOAuthProxySession):
                self._consume_gemini_state(normalized_state)
                raise ValueError("OAuth callback session does not support Gemini callback")

            self._consume_gemini_state(normalized_state)
            self._mark_oauth_callback_received(session)
            session.updated_at = _utc_now()

            if error and error.strip():
                session.status = "failed"
                session.error = f"OAuth callback error: {error.strip()}"
                session.auth_ready = self._collect_auth_ready(session.engine)
                self._finalize_active_session(session)
                return self._to_snapshot(session)

            normalized_code = (code or "").strip()
            if not normalized_code:
                session.status = "failed"
                session.error = "OAuth callback code is missing"
                session.auth_ready = self._collect_auth_ready(session.engine)
                self._finalize_active_session(session)
                return self._to_snapshot(session)

            try:
                flow_result = self._gemini_oauth_proxy_flow.complete_with_code(
                    runtime=runtime,
                    code=normalized_code,
                    state=normalized_state,
                )
                session.status = "succeeded"
                session.error = None
                session.auth_ready = self._collect_auth_ready("gemini")
                self._mark_auto_callback_success(session)
                audit = self._ensure_audit_dict(session)
                audit["callback_mode"] = "auto"
                audit.update(flow_result)
            except Exception as exc:
                session.status = "failed"
                session.error = f"OAuth callback token exchange failed: {exc}"
                session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return self._to_snapshot(session)

    def complete_iflow_callback(
        self,
        *,
        state: str,
        code: str | None = None,
        error: str | None = None,
    ) -> Dict[str, Any]:
        normalized_state = state.strip()
        if not normalized_state:
            raise ValueError("OAuth callback state is required")

        with self._lock:
            if normalized_state in self._iflow_callback_state_consumed:
                raise ValueError("OAuth callback state has already been consumed")
            session_id = self._resolve_iflow_state(normalized_state)
            if session_id is None:
                raise ValueError("OAuth callback state is invalid")
            session = self._sessions.get(session_id)
            if session is None:
                self._consume_iflow_state(normalized_state)
                raise ValueError("OAuth callback session not found")

            self._refresh_session_locked(session)
            if session.status in _TERMINAL_STATUSES:
                self._consume_iflow_state(normalized_state)
                raise ValueError("OAuth callback session is already finished")

            runtime = session.driver_state
            if not isinstance(runtime, IFlowOAuthProxySession):
                self._consume_iflow_state(normalized_state)
                raise ValueError("OAuth callback session does not support iFlow callback")

            self._consume_iflow_state(normalized_state)
            self._mark_oauth_callback_received(session)
            session.updated_at = _utc_now()

            if error and error.strip():
                session.status = "failed"
                session.error = f"OAuth callback error: {error.strip()}"
                session.auth_ready = self._collect_auth_ready(session.engine)
                self._finalize_active_session(session)
                return self._to_snapshot(session)

            normalized_code = (code or "").strip()
            if not normalized_code:
                session.status = "failed"
                session.error = "OAuth callback code is missing"
                session.auth_ready = self._collect_auth_ready(session.engine)
                self._finalize_active_session(session)
                return self._to_snapshot(session)

            try:
                flow_result = self._iflow_oauth_proxy_flow.complete_with_code(
                    runtime=runtime,
                    code=normalized_code,
                    state=normalized_state,
                )
                session.status = "succeeded"
                session.error = None
                session.auth_ready = self._collect_auth_ready("iflow")
                self._mark_auto_callback_success(session)
                audit = self._ensure_audit_dict(session)
                audit["callback_mode"] = "auto"
                audit.update(flow_result)
            except Exception as exc:
                session.status = "failed"
                session.error = f"OAuth callback token exchange failed: {exc}"
                session.auth_ready = self._collect_auth_ready(session.engine)
            self._finalize_active_session(session)
            return self._to_snapshot(session)

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
        normalized_kind = kind.strip().lower()
        if normalized_kind not in {"code", "api_key", "text"}:
            raise ValueError("Unsupported input kind")
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(session_id)
            self._refresh_session_locked(session)
            self._append_session_event(
                session,
                "input_received",
                {
                    "kind": normalized_kind,
                    "value_redacted": True,
                },
            )
            runtime = session.driver_state
            if session.engine == "codex":
                if normalized_kind not in {"code", "text"}:
                    raise ValueError("Codex auth only accepts code/text input")
                if isinstance(runtime, CodexOAuthProxySession):
                    self._mark_manual_fallback(session)
                    session.status = "code_submitted_waiting_result"
                    session.updated_at = _utc_now()
                    try:
                        self._codex_oauth_proxy_flow.submit_input(runtime, value)
                        session.status = "succeeded"
                        session.error = None
                        session.auth_ready = self._collect_auth_ready("codex")
                        self._finalize_active_session(session)
                    except Exception as exc:
                        session.status = "failed"
                        session.error = str(exc)
                        session.auth_ready = self._collect_auth_ready("codex")
                        self._finalize_active_session(session)
                elif isinstance(runtime, OpenAIDeviceProxySession):
                    raise ValueError("Codex auth_code_or_url device session does not accept manual input")
                else:
                    self._submit_codex_input(session, value)
            elif session.engine == "gemini":
                if normalized_kind not in {"code", "text"}:
                    raise ValueError("Gemini auth only accepts code/text input")
                if isinstance(runtime, GeminiOAuthProxySession):
                    self._mark_manual_fallback(session)
                    session.status = "code_submitted_waiting_result"
                    session.updated_at = _utc_now()
                    try:
                        flow_result = self._gemini_oauth_proxy_flow.submit_input(runtime, value)
                        session.status = "succeeded"
                        session.error = None
                        session.auth_ready = self._collect_auth_ready("gemini")
                        audit = self._ensure_audit_dict(session)
                        audit["callback_mode"] = "manual"
                        audit.update(flow_result)
                        self._finalize_active_session(session)
                    except Exception as exc:
                        session.status = "failed"
                        session.error = str(exc)
                        session.auth_ready = self._collect_auth_ready("gemini")
                        self._finalize_active_session(session)
                else:
                    if runtime is None or not isinstance(runtime, GeminiAuthCliSession):
                        raise ValueError("Input is only supported for active delegated auth sessions")
                    self._gemini_flow.submit_code(runtime, value)
            elif session.engine == "iflow":
                if normalized_kind not in {"code", "text"}:
                    raise ValueError("iFlow auth only accepts code/text input")
                if isinstance(runtime, IFlowOAuthProxySession):
                    self._mark_manual_fallback(session)
                    session.status = "code_submitted_waiting_result"
                    session.updated_at = _utc_now()
                    try:
                        flow_result = self._iflow_oauth_proxy_flow.submit_input(runtime, value)
                        session.status = "succeeded"
                        session.error = None
                        session.auth_ready = self._collect_auth_ready("iflow")
                        audit = self._ensure_audit_dict(session)
                        audit["callback_mode"] = "manual"
                        audit.update(flow_result)
                        self._finalize_active_session(session)
                    except Exception as exc:
                        session.status = "failed"
                        session.error = str(exc)
                        session.auth_ready = self._collect_auth_ready("iflow")
                        self._finalize_active_session(session)
                else:
                    if runtime is None or not isinstance(runtime, IFlowAuthCliSession):
                        raise ValueError("Input is only supported for active delegated auth sessions")
                    self._iflow_flow.submit_code(runtime, value)
            elif session.engine == "opencode":
                if session.input_kind == "api_key":
                    if normalized_kind != "api_key":
                        raise ValueError("OpenCode API key flow only accepts api_key input")
                    if not session.provider_id:
                        raise ValueError("OpenCode provider is missing")
                    auth_store = self._build_opencode_auth_store()
                    auth_store.upsert_api_key(session.provider_id, value)
                    session.status = "succeeded"
                    session.updated_at = _utc_now()
                    session.auth_ready = self._collect_auth_ready("opencode")
                    session.error = None
                    self._finalize_active_session(session)
                else:
                    if normalized_kind not in {"code", "text"}:
                        raise ValueError("OpenCode OAuth flow only accepts text/code input")
                    if isinstance(runtime, OpencodeOpenAIOAuthProxySession):
                        self._mark_manual_fallback(session)
                        session.status = "code_submitted_waiting_result"
                        session.updated_at = _utc_now()
                        try:
                            self._opencode_openai_oauth_proxy_flow.submit_input(runtime, value)
                            session.status = "succeeded"
                            session.error = None
                            session.auth_ready = self._collect_auth_ready("opencode")
                            self._finalize_active_session(session)
                        except Exception as exc:
                            session.status = "failed"
                            session.error = str(exc)
                            session.auth_ready = self._collect_auth_ready("opencode")
                            self._finalize_active_session(session)
                    elif isinstance(runtime, OpencodeGoogleAntigravityOAuthProxySession):
                        self._mark_manual_fallback(session)
                        session.status = "code_submitted_waiting_result"
                        session.updated_at = _utc_now()
                        try:
                            flow_result = self._opencode_google_antigravity_oauth_proxy_flow.submit_input(runtime, value)
                            session.status = "succeeded"
                            session.error = None
                            session.auth_ready = self._collect_auth_ready("opencode")
                            audit = self._ensure_audit_dict(session)
                            audit.update(flow_result)
                            audit["callback_mode"] = "manual"
                            self._finalize_active_session(session)
                        except Exception as exc:
                            session.status = "failed"
                            session.error = str(exc)
                            session.auth_ready = self._collect_auth_ready("opencode")
                            self._finalize_active_session(session)
                    elif isinstance(runtime, OpenAIDeviceProxySession):
                        raise ValueError("OpenCode OpenAI auth_code_or_url device session does not accept manual input")
                    else:
                        if runtime is None or not isinstance(runtime, OpencodeAuthCliSession):
                            raise ValueError("Input is only supported for active delegated auth sessions")
                        self._opencode_flow.submit_input(runtime, value)
            else:
                raise ValueError("Input is not supported for this auth session")
            self._refresh_session_locked(session)
            return self._to_snapshot(session)


engine_auth_flow_manager = EngineAuthFlowManager()
