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

from ..config import config
from .agent_cli_manager import AgentCliManager
from .engine_interaction_gate import (
    EngineInteractionBusyError,
    EngineInteractionGate,
    engine_interaction_gate,
)
from .gemini_auth_cli_flow import GeminiAuthCliFlow, GeminiAuthCliSession
from .iflow_auth_cli_flow import IFlowAuthCliFlow, IFlowAuthCliSession
from .opencode_auth_cli_flow import OpencodeAuthCliFlow, OpencodeAuthCliSession
from .opencode_auth_provider_registry import (
    OpencodeAuthProvider,
    opencode_auth_provider_registry,
)
from .opencode_auth_store import OpencodeAuthStore
from .run_folder_trust_manager import run_folder_trust_manager

_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_CODE_PATTERN = re.compile(r"\b[A-Z0-9]{4}(?:-[A-Z0-9]{4,})+\b")
_TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "expired"}
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
    driver_state: GeminiAuthCliSession | IFlowAuthCliSession | OpencodeAuthCliSession | None = None
    audit: Dict[str, Any] | None = None
    trust_engine: Optional[str] = None
    trust_path: Optional[Path] = None


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
        self._iflow_flow = IFlowAuthCliFlow()
        self._opencode_flow = OpencodeAuthCliFlow()

    def _enabled(self) -> bool:
        return bool(config.SYSTEM.ENGINE_AUTH_DEVICE_PROXY_ENABLED)

    def _ttl_seconds(self) -> int:
        raw = int(config.SYSTEM.ENGINE_AUTH_DEVICE_PROXY_TTL_SECONDS)
        return max(60, raw)

    def _session_root(self) -> Path:
        return self.agent_manager.profile.data_dir / "engine_auth_sessions"

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
        self._rollback_google_antigravity_if_needed(session)
        if self._active_session_id == session.session_id:
            self._active_session_id = None
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
        match = _URL_PATTERN.search(sanitized)
        if not match:
            return None
        return match.group(0).strip().rstrip(".,);")

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

    def _refresh_session_locked(self, session: _AuthSession) -> None:
        if session.driver == "gemini":
            self._refresh_gemini_session_locked(session)
            return
        if session.driver == "iflow":
            self._refresh_iflow_session_locked(session)
            return
        if session.driver == "opencode":
            self._refresh_opencode_session_locked(session)
            return

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
        session.user_code = None
        session.error = runtime.error
        session.exit_code = runtime.exit_code
        session.auth_ready = self._collect_auth_ready(session.engine)
        if session.status == "failed" and session.exit_code == 0 and session.auth_ready:
            session.status = "succeeded"
            session.error = None

        if runtime.status in _TERMINAL_STATUSES:
            if runtime.status == "succeeded":
                session.auth_ready = True
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
        return {
            "session_id": session.session_id,
            "engine": session.engine,
            "method": session.method,
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
        method: str = "device-auth",
        provider_id: str | None = None,
    ) -> Dict[str, Any]:
        if not self._enabled():
            raise ValueError("Engine auth device proxy is disabled")

        normalized_engine = engine.strip().lower()
        normalized_method = method.strip().lower()
        normalized_provider = provider_id.strip().lower() if provider_id else None
        provider: OpencodeAuthProvider | None = None
        if normalized_engine == "codex":
            if normalized_method != "device-auth":
                raise ValueError("Unsupported auth method for codex: only 'device-auth' is allowed")
        elif normalized_engine == "gemini":
            if normalized_method != "screen-reader-google-oauth":
                raise ValueError(
                    "Unsupported auth method for gemini: only 'screen-reader-google-oauth' is allowed"
                )
        elif normalized_engine == "iflow":
            if normalized_method != "iflow-cli-oauth":
                raise ValueError(
                    "Unsupported auth method for iflow: only 'iflow-cli-oauth' is allowed"
                )
        elif normalized_engine == "opencode":
            if normalized_method != "opencode-provider-auth":
                raise ValueError(
                    "Unsupported auth method for opencode: only 'opencode-provider-auth' is allowed"
                )
            if not normalized_provider:
                raise ValueError("provider_id is required for opencode auth sessions")
            provider = opencode_auth_provider_registry.get(normalized_provider)
        else:
            raise ValueError("Unsupported engine for auth proxy")

        command = self.agent_manager.resolve_engine_command(normalized_engine)
        if command is None:
            raise RuntimeError(f"{normalized_engine} CLI not found")

        session_id = str(uuid.uuid4())
        with self._lock:
            if self._active_session_id:
                active = self._sessions.get(self._active_session_id)
                if active is not None:
                    self._refresh_session_locked(active)
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

            session_dir = self._session_root() / session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            trust_engine: str | None = None
            trust_path: Path | None = None
            output_name = (
                "codex_device_auth.log"
                if normalized_engine == "codex"
                else (
                    "gemini_screen_reader_auth.log"
                    if normalized_engine == "gemini"
                    else (
                        "iflow_cli_auth.log"
                        if normalized_engine == "iflow"
                        else "opencode_provider_auth.log"
                    )
                )
            )
            output_path = session_dir / output_name
            output_path.touch()

            env = self.agent_manager.profile.build_subprocess_env(os.environ.copy())
            env.setdefault("TERM", "xterm-256color")
            now = _utc_now()
            expires_at = now + timedelta(seconds=self._ttl_seconds())

            try:
                trust_engine, trust_path = self._inject_trust_for_session(
                    normalized_engine,
                    session_dir,
                )
                if normalized_engine == "codex":
                    with output_path.open("w", encoding="utf-8") as stream:
                        process = subprocess.Popen(
                            [str(command), "login", "--device-auth"],
                            cwd=str(session_dir),
                            env=env,
                            stdout=stream,
                            stderr=subprocess.STDOUT,
                            text=True,
                            start_new_session=True,
                        )
                    session = _AuthSession(
                        session_id=session_id,
                        engine=normalized_engine,
                        method=normalized_method,
                        provider_id=None,
                        provider_name=None,
                        created_at=now,
                        updated_at=now,
                        expires_at=expires_at,
                        status="starting",
                        output_path=output_path,
                        process=process,
                        driver="codex",
                        trust_engine=trust_engine,
                        trust_path=trust_path,
                    )
                elif normalized_engine == "gemini":
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
                                trust_engine=trust_engine,
                                trust_path=trust_path,
                            )
                            self._sessions[session_id] = session
                            self._finalize_active_session(session)
                            return self._to_snapshot(session)

                    if provider.auth_mode == "api_key":
                        session = _AuthSession(
                            session_id=session_id,
                            engine=normalized_engine,
                            method=normalized_method,
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
                            audit=audit or None,
                            trust_engine=trust_engine,
                            trust_path=trust_path,
                        )
                    else:
                        runtime = self._opencode_flow.start_session(
                            session_id=session_id,
                            command_path=command,
                            cwd=session_dir,
                            env=env,
                            output_path=output_path,
                            expires_at=expires_at,
                            provider_id=provider.provider_id,
                            provider_label=provider.menu_label,
                        )
                        session = _AuthSession(
                            session_id=session_id,
                            engine=normalized_engine,
                            method=normalized_method,
                            provider_id=provider.provider_id,
                            provider_name=provider.display_name,
                            created_at=now,
                            updated_at=now,
                            expires_at=expires_at,
                            status="starting",
                            input_kind="text",
                            output_path=output_path,
                            process=runtime.process,
                            driver="opencode",
                            driver_state=runtime,
                            audit=audit or None,
                            trust_engine=trust_engine,
                            trust_path=trust_path,
                        )
            except Exception:
                if trust_engine and trust_path:
                    try:
                        self.trust_manager.remove_run_folder(trust_engine, trust_path)
                    except Exception:
                        pass
                self.interaction_gate.release("auth_flow", session_id)
                raise
            self._sessions[session_id] = session
            self._active_session_id = session_id
            self._refresh_session_locked(session)
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
                self._terminate_process(session)
                session.status = "canceled"
                session.updated_at = _utc_now()
                session.auth_ready = (
                    self._collect_auth_ready(session.engine)
                    if session.engine in {"codex", "opencode"}
                    else False
                )
                session.error = session.error or "Canceled by user"
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
            runtime = session.driver_state
            if session.engine == "gemini":
                if runtime is None or not isinstance(runtime, GeminiAuthCliSession):
                    raise ValueError("Input is only supported for active delegated auth sessions")
                if normalized_kind not in {"code", "text"}:
                    raise ValueError("Gemini auth only accepts code/text input")
                self._gemini_flow.submit_code(runtime, value)
            elif session.engine == "iflow":
                if runtime is None or not isinstance(runtime, IFlowAuthCliSession):
                    raise ValueError("Input is only supported for active delegated auth sessions")
                if normalized_kind not in {"code", "text"}:
                    raise ValueError("iFlow auth only accepts code/text input")
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
                    if runtime is None or not isinstance(runtime, OpencodeAuthCliSession):
                        raise ValueError("Input is only supported for active delegated auth sessions")
                    if normalized_kind not in {"code", "text"}:
                        raise ValueError("OpenCode OAuth flow only accepts text/code input")
                    self._opencode_flow.submit_input(runtime, value)
            else:
                raise ValueError("Input is not supported for this auth session")
            self._refresh_session_locked(session)
            return self._to_snapshot(session)


engine_auth_flow_manager = EngineAuthFlowManager()
