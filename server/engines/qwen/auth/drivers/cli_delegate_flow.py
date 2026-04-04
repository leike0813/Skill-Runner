from __future__ import annotations

import errno
import os
import platform
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from urllib.parse import parse_qs, urlsplit

from server.runtime.auth.cli_pty_runtime import CliPtyRuntime, ProcessHandle, spawn_cli_pty

_ANSI_CSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_ANSI_OSC_PATTERN = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)")
_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_USER_CODE_PATTERN = re.compile(r"\b[A-Z0-9]{4,}(?:-[A-Z0-9]{4,})*\b")
_TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "expired"}
_QWEN_OAUTH_SUCCESS = "Successfully authenticated with Qwen OAuth."
_QWEN_OAUTH_FAILURE = "Failed to authenticate with Qwen OAuth:"
_QWEN_OAUTH_WAITING = "Waiting for authorization..."
_QWEN_OAUTH_URL_HINT = "Please visit the following URL in your browser to authorize:"
_CODING_PLAN_REGION_PROMPT = "Select region for Coding Plan:"
_CODING_PLAN_API_KEY_PROMPT = "Enter your Coding Plan API key:"
_CODING_PLAN_SUCCESS = "Successfully authenticated with Alibaba Cloud Coding Plan."
_CODING_PLAN_FAILURE = "Failed to authenticate with Coding Plan:"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _strip_ansi(text: str) -> str:
    cleaned = _ANSI_OSC_PATTERN.sub("", text)
    cleaned = _ANSI_CSI_PATTERN.sub("", cleaned)
    return cleaned


@dataclass
class QwenAuthCliSession:
    session_id: str
    provider_id: str
    process: ProcessHandle
    master_fd: int
    output_path: Path
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    status: str = "starting"
    auth_url: str | None = None
    user_code: str | None = None
    error: str | None = None
    exit_code: int | None = None
    saw_output: bool = False
    region_selected: bool = False
    region_selection_sent_at: float = 0.0
    api_key_prompt_visible: bool = False
    api_key_submitted: bool = False
    api_key_submitted_at: float = 0.0
    saw_success_marker: bool = False
    saw_failure_marker: bool = False
    _closed_fd: bool = False
    _clean_buffer: str = ""
    _line_tail: list[str] = field(default_factory=list)
    _reader_thread: Thread | None = None
    pty_runtime: CliPtyRuntime | None = None
    _lock: Lock = field(default_factory=Lock, repr=False)


class QwenAuthCliFlow:
    def __init__(self, agent_home: Path) -> None:
        self.agent_home = agent_home

    def start_session(
        self,
        *,
        session_id: str,
        command_path: Path,
        cwd: Path,
        env: dict[str, str],
        output_path: Path,
        expires_at: datetime,
        provider_id: str,
    ) -> QwenAuthCliSession:
        command = self._build_command(command_path=command_path, provider_id=provider_id)
        runtime = spawn_cli_pty(
            command=command,
            cwd=cwd,
            env=env,
        )
        now = _utc_now()
        session = QwenAuthCliSession(
            session_id=session_id,
            provider_id=provider_id,
            process=runtime.process,
            master_fd=runtime.master_fd,
            output_path=output_path,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            pty_runtime=runtime,
        )
        reader = Thread(target=self._reader_loop, args=(session,), daemon=True)
        session._reader_thread = reader
        reader.start()
        return session

    def refresh(self, session: QwenAuthCliSession) -> None:
        with session._lock:
            now = _utc_now()
            session.updated_at = now
            if session.status in _TERMINAL_STATUSES:
                return
            self._consume_output_locked(session)
            if session.status in _TERMINAL_STATUSES:
                return
            if now > session.expires_at:
                self._terminate_process_locked(session)
                session.status = "expired"
                session.error = "Auth session expired"
                return

            rc = session.process.poll()
            if rc is None:
                if session.provider_id == "qwen-oauth" and (
                    session.auth_url or _QWEN_OAUTH_WAITING in session._clean_buffer
                ):
                    session.status = "waiting_user"
                return

            session.exit_code = rc
            if session.status == "succeeded":
                return
            if session.status == "canceled":
                return
            if rc == 0 and session.saw_success_marker:
                session.status = "succeeded"
                session.error = None
                return
            session.status = "failed"
            session.error = self._build_error_summary_locked(
                session,
                fallback=f"qwen auth exited with code {rc}",
            )

    def submit_api_key(self, session: QwenAuthCliSession, api_key: str) -> None:
        normalized = api_key.strip()
        if not normalized:
            raise ValueError("API key is required")
        with session._lock:
            if session.provider_id == "qwen-oauth":
                raise ValueError("Qwen OAuth delegated auth does not accept UI input")
            if session.status in _TERMINAL_STATUSES:
                raise ValueError("Auth session already finished")
            if session.status not in {"waiting_user", "code_submitted_waiting_result"}:
                raise ValueError("Qwen Coding Plan session is not ready for API key input")
            self._write_input_locked(session, normalized + "\r")
            session.api_key_submitted = True
            session.api_key_submitted_at = time.monotonic()
            session.status = "code_submitted_waiting_result"
            session.error = None
            session.updated_at = _utc_now()

    def cancel(self, session: QwenAuthCliSession) -> None:
        with session._lock:
            if session.status in _TERMINAL_STATUSES:
                return
            self._terminate_process_locked(session)
            session.status = "canceled"
            session.error = session.error or "Canceled by user"
            session.updated_at = _utc_now()

    def _build_command(self, *, command_path: Path, provider_id: str) -> list[str]:
        if provider_id == "qwen-oauth":
            return [str(command_path), "auth", "qwen-oauth"]
        if provider_id.startswith("coding-plan-"):
            return [str(command_path), "auth", "coding-plan"]
        raise ValueError(f"Unknown provider: {provider_id}")

    def _reader_loop(self, session: QwenAuthCliSession) -> None:
        while True:
            try:
                runtime = session.pty_runtime
                if runtime is None:
                    chunk = os.read(session.master_fd, 4096)
                else:
                    chunk = runtime.read(4096)
            except OSError as exc:
                err_no = getattr(exc, "errno", None)
                if err_no not in {None, errno.EBADF, errno.EIO}:
                    with session._lock:
                        if session.status not in _TERMINAL_STATUSES:
                            session.error = session.error or f"PTY read error: {exc}"
                break
            if not chunk:
                break
            text = chunk.decode("utf-8", errors="replace")
            with session._lock:
                session.updated_at = _utc_now()
                self._append_output_locked(session, text)
                self._consume_output_locked(session)

    def _append_output_locked(self, session: QwenAuthCliSession, chunk: str) -> None:
        session.saw_output = True
        try:
            with session.output_path.open("a", encoding="utf-8") as stream:
                stream.write(chunk)
        except OSError:
            pass

        cleaned = _strip_ansi(chunk).replace("\r", "\n")
        session._clean_buffer = (session._clean_buffer + cleaned)[-30000:]
        for row in cleaned.splitlines():
            line = row.strip()
            if not line:
                continue
            session._line_tail.append(line)
            if len(session._line_tail) > 40:
                session._line_tail = session._line_tail[-40:]

    def _consume_output_locked(self, session: QwenAuthCliSession) -> None:
        if session.status in _TERMINAL_STATUSES:
            return
        window = session._clean_buffer

        auth_url = self._extract_auth_url(window)
        if auth_url:
            session.auth_url = auth_url
        user_code = self._extract_user_code(window, auth_url)
        if user_code:
            session.user_code = user_code

        if session.provider_id == "qwen-oauth":
            if _QWEN_OAUTH_FAILURE in window:
                session.saw_failure_marker = True
                session.status = "failed"
                session.error = self._build_error_summary_locked(
                    session,
                    fallback="Qwen OAuth authentication failed",
                )
                return
            if _QWEN_OAUTH_SUCCESS in window:
                session.saw_success_marker = True
                session.status = "succeeded"
                session.error = None
                return
            if session.auth_url or _QWEN_OAUTH_WAITING in window or _QWEN_OAUTH_URL_HINT in window:
                session.status = "waiting_user"
            return

        if _CODING_PLAN_FAILURE in window:
            session.saw_failure_marker = True
            session.status = "failed"
            session.error = self._build_error_summary_locked(
                session,
                fallback="Coding Plan authentication failed",
            )
            return
        if _CODING_PLAN_SUCCESS in window:
            session.saw_success_marker = True
            session.status = "succeeded"
            session.error = None
            return

        if _CODING_PLAN_REGION_PROMPT in window and not session.region_selected:
            now = time.monotonic()
            if now - session.region_selection_sent_at >= 0.8:
                if session.provider_id == "coding-plan-global":
                    self._write_input_locked(session, "\x1b[B")
                self._write_input_locked(session, "\r")
                session.region_selected = True
                session.region_selection_sent_at = now
            session.status = "waiting_orchestrator"
            return

        if _CODING_PLAN_API_KEY_PROMPT in window:
            session.api_key_prompt_visible = True
            if session.api_key_submitted:
                session.status = "code_submitted_waiting_result"
            else:
                session.status = "waiting_user"
            return

        if session.api_key_submitted:
            session.status = "code_submitted_waiting_result"

    def _extract_auth_url(self, text: str) -> str | None:
        matches = [
            match.group(0).strip().rstrip(".,);")
            for match in _URL_PATTERN.finditer(text)
        ]
        if not matches:
            return None
        for candidate in reversed(matches):
            try:
                host = (urlsplit(candidate).hostname or "").lower()
            except ValueError:
                host = ""
            if host not in {"localhost", "127.0.0.1", "::1"}:
                return candidate
        return matches[-1]

    def _extract_user_code(self, text: str, auth_url: str | None) -> str | None:
        if auth_url:
            try:
                query = parse_qs(urlsplit(auth_url).query)
            except ValueError:
                query = {}
            for key in ("user_code", "code"):
                values = query.get(key)
                if values:
                    candidate = values[0].strip().upper()
                    if candidate:
                        return candidate
        for line in text.splitlines():
            lowered = line.lower()
            if "code" not in lowered and "authorize" not in lowered and "device" not in lowered:
                continue
            match = _USER_CODE_PATTERN.search(line.upper())
            if match:
                return match.group(0)
        return None

    def _build_error_summary_locked(self, session: QwenAuthCliSession, *, fallback: str) -> str:
        rows = [line.strip() for line in session._line_tail if line.strip()]
        if not rows:
            return fallback
        return " | ".join(rows[-3:])

    def _write_input_locked(self, session: QwenAuthCliSession, text: str) -> None:
        runtime = session.pty_runtime
        if runtime is not None:
            runtime.write(text)
            return
        os.write(session.master_fd, text.encode("utf-8", errors="replace"))

    def _terminate_process_locked(self, session: QwenAuthCliSession) -> None:
        runtime = session.pty_runtime
        try:
            if runtime is not None:
                runtime.close()
            elif not session._closed_fd:
                os.close(session.master_fd)
        except OSError:
            pass
        session._closed_fd = True
        process = session.process
        if process.poll() is not None:
            return
        system_name = platform.system().lower()
        try:
            if system_name.startswith("win"):
                os.kill(process.pid, signal.SIGTERM)
            else:
                os.killpg(process.pid, signal.SIGTERM)
        except OSError:
            return
        deadline = time.time() + 1.5
        while time.time() < deadline:
            if process.poll() is not None:
                return
            time.sleep(0.05)
        try:
            if system_name.startswith("win"):
                os.kill(process.pid, signal.SIGKILL)
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
