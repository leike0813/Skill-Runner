import errno
import os
import platform
import pty
import re
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Any

_ANSI_CSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_ANSI_OSC_PATTERN = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)")
_URL_PATTERN = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "expired"}

_MENU_ANCHOR = "How would you like to authenticate for this project?"
_MENU_ENTER_HINT = "(Use Enter to select)"
_URL_ANCHOR = "Please visit the following URL to authorize the application:"
_CODE_PROMPT_ANCHOR = "Enter the authorization code:"
_MAIN_UI_ANCHOR = "Type your message or @path/to/file"
_TRUST_PROMPT_ANCHOR = "Do you trust this folder?"
_API_KEY_PROMPT_ANCHOR = "Enter Gemini API Key"
_API_KEY_PASTE_ANCHOR = "Paste your API key here"
_API_KEY_HINT_ANCHOR = "Esc to cancel"
_MENU_ACTION_COOLDOWN_SECONDS = 0.6
_REAUTH_INITIAL_DELAY_SECONDS = 2.0
_REAUTH_CONFIRM_DELAY_SECONDS = 2.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _strip_ansi(text: str) -> str:
    cleaned = _ANSI_OSC_PATTERN.sub("", text)
    cleaned = _ANSI_CSI_PATTERN.sub("", cleaned)
    return cleaned


@dataclass
class GeminiAuthCliSession:
    session_id: str
    process: subprocess.Popen[Any]
    master_fd: int
    output_path: Path
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    status: str = "starting"
    auth_url: str | None = None
    error: str | None = None
    exit_code: int | None = None
    reauth_requested: bool = False
    reauth_requested_at: float = 0.0
    reauth_attempts: int = 0
    main_ui_seen_at: float = 0.0
    reauth_confirm_sent: bool = False
    reauth_confirmed_at: float = 0.0
    menu_selection_confirmed: bool = False
    saw_auth_menu: bool = False
    saw_auth_url: bool = False
    menu_entered_at: float = 0.0
    menu_navigated_at: float = 0.0
    menu_last_checked_option: int | None = None
    trust_prompt_entered_at: float = 0.0
    api_key_escape_sent_at: float = 0.0
    code_submitted: bool = False
    saw_output: bool = False
    _closed_fd: bool = False
    _clean_buffer: str = ""
    _line_tail: list[str] = field(default_factory=list)
    _reader_thread: Thread | None = None
    _lock: Lock = field(default_factory=Lock, repr=False)


class GeminiAuthCliFlow:
    def start_session(
        self,
        *,
        session_id: str,
        command_path: Path,
        cwd: Path,
        env: dict[str, str],
        output_path: Path,
        expires_at: datetime,
    ) -> GeminiAuthCliSession:
        master_fd, slave_fd = pty.openpty()
        try:
            process = subprocess.Popen(
                [str(command_path), "--screen-reader"],
                cwd=str(cwd),
                env=env,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=False,
                start_new_session=True,
            )
        finally:
            try:
                os.close(slave_fd)
            except OSError:
                pass

        now = _utc_now()
        session = GeminiAuthCliSession(
            session_id=session_id,
            process=process,
            master_fd=master_fd,
            output_path=output_path,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        reader = Thread(target=self._reader_loop, args=(session,), daemon=True)
        session._reader_thread = reader
        reader.start()
        return session

    def refresh(self, session: GeminiAuthCliSession) -> None:
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
                return

            session.exit_code = rc
            if session.status == "succeeded":
                return
            summary = self._build_error_summary_locked(session)
            session.status = "failed"
            session.error = summary or f"gemini auth exited with code {rc}"

    def submit_code(self, session: GeminiAuthCliSession, code: str) -> None:
        normalized = code.strip()
        if not normalized:
            raise ValueError("Authorization code is required")
        with session._lock:
            if session.status in _TERMINAL_STATUSES:
                raise ValueError("Auth session already finished")
            if session.status not in {"waiting_user", "code_submitted_waiting_result"}:
                raise ValueError("Gemini auth session is not waiting for authorization code")
            self._write_input_locked(session, normalized + "\r")
            session.code_submitted = True
            session.status = "code_submitted_waiting_result"
            session.updated_at = _utc_now()

    def cancel(self, session: GeminiAuthCliSession) -> None:
        with session._lock:
            if session.status in _TERMINAL_STATUSES:
                return
            self._terminate_process_locked(session)
            session.status = "canceled"
            session.error = session.error or "Canceled by user"
            session.updated_at = _utc_now()

    def _reader_loop(self, session: GeminiAuthCliSession) -> None:
        while True:
            try:
                chunk = os.read(session.master_fd, 4096)
            except OSError as exc:
                if exc.errno not in {errno.EBADF, errno.EIO}:
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

    def _append_output_locked(self, session: GeminiAuthCliSession, chunk: str) -> None:
        session.saw_output = True
        try:
            with session.output_path.open("a", encoding="utf-8") as stream:
                stream.write(chunk)
        except Exception:
            pass

        cleaned = _strip_ansi(chunk).replace("\r", "\n")
        session._clean_buffer = (session._clean_buffer + cleaned)[-20000:]
        for row in cleaned.splitlines():
            line = row.strip()
            if not line:
                continue
            session._line_tail.append(line)
            if len(session._line_tail) > 20:
                session._line_tail = session._line_tail[-20:]

    def _consume_output_locked(self, session: GeminiAuthCliSession) -> None:
        if session.status in _TERMINAL_STATUSES:
            return
        window = session._clean_buffer
        main_idx = window.rfind(_MAIN_UI_ANCHOR)
        menu_idx = window.rfind(_MENU_ANCHOR)
        url_idx = window.rfind(_URL_ANCHOR)
        code_idx = window.rfind(_CODE_PROMPT_ANCHOR)
        trust_idx = window.rfind(_TRUST_PROMPT_ANCHOR)
        api_key_idx = max(
            window.rfind(_API_KEY_PROMPT_ANCHOR),
            window.rfind(_API_KEY_PASTE_ANCHOR),
            window.rfind(_API_KEY_HINT_ANCHOR),
        )
        latest_stage_idx = max(main_idx, menu_idx, url_idx, code_idx, trust_idx, api_key_idx)
        main_visible = main_idx >= 0 and main_idx == latest_stage_idx
        menu_visible = menu_idx >= 0 and menu_idx == latest_stage_idx
        trust_visible = trust_idx >= 0 and trust_idx == latest_stage_idx
        api_key_visible = api_key_idx >= 0 and api_key_idx == latest_stage_idx
        code_prompt_visible = code_idx >= 0 and code_idx == latest_stage_idx
        url_visible = url_idx >= 0 and url_idx == latest_stage_idx

        if url_visible or code_prompt_visible:
            auth_url = self._extract_auth_url(window)
            if auth_url and auth_url != session.auth_url:
                session.auth_url = auth_url
                session.saw_auth_url = True
                # A new URL always means waiting for user-provided authorization code.
                session.code_submitted = False
                session.status = "waiting_user"
            elif code_prompt_visible and not session.code_submitted:
                session.status = "waiting_user"

        if code_prompt_visible:
            if session.status == "succeeded":
                return
            if session.code_submitted:
                session.status = "code_submitted_waiting_result"
            else:
                session.status = "waiting_user"
            # Once code prompt appears, stop sending any automation keystrokes.
            return

        if api_key_visible and not session.code_submitted:
            now = time.monotonic()
            if now - session.api_key_escape_sent_at >= 0.8:
                self._write_input_locked(session, "\x1b")
                session.api_key_escape_sent_at = now

        if trust_visible:
            now = time.monotonic()
            if now - session.trust_prompt_entered_at >= 0.8:
                self._write_input_locked(session, "\r")
                session.trust_prompt_entered_at = now

        if menu_visible and _MENU_ENTER_HINT in window and not session.saw_auth_url:
            session.saw_auth_menu = True
            now = time.monotonic()
            checked = self._extract_checked_option(window)
            if checked is not None and checked > 1:
                # Ensure "Login with Google" is selected before confirming.
                if (
                    checked != session.menu_last_checked_option
                    and now - session.menu_navigated_at >= _MENU_ACTION_COOLDOWN_SECONDS
                ):
                    self._write_input_locked(session, "\x1b[A" * (checked - 1))
                    session.menu_navigated_at = now
                    session.menu_last_checked_option = checked
                    session.menu_selection_confirmed = False
                elif (
                    not session.menu_selection_confirmed
                    and now - session.menu_entered_at >= _MENU_ACTION_COOLDOWN_SECONDS
                ):
                    # Fallback: if screen does not repaint checked marker, still confirm.
                    self._write_input_locked(session, "\r")
                    session.menu_entered_at = now
                    session.menu_selection_confirmed = True
            elif (
                not session.menu_selection_confirmed
                and now - session.menu_entered_at >= _MENU_ACTION_COOLDOWN_SECONDS
            ):
                self._write_input_locked(session, "\r")
                session.menu_entered_at = now
                session.menu_last_checked_option = checked
                session.menu_selection_confirmed = True
            if session.status == "starting":
                session.status = "waiting_orchestrator"

        if main_visible:
            if session.code_submitted:
                session.status = "succeeded"
                session.error = None
                return
            if session.saw_auth_url:
                return
            now = time.monotonic()
            if session.main_ui_seen_at <= 0.0:
                session.main_ui_seen_at = now
            if not session.reauth_requested:
                if now - session.main_ui_seen_at >= _REAUTH_INITIAL_DELAY_SECONDS:
                    self._write_input_locked(session, "/auth\r")
                    session.reauth_requested = True
                    session.reauth_requested_at = now
                    session.reauth_attempts += 1
                    session.menu_selection_confirmed = False
                    session.saw_auth_menu = False
                    if session.status == "starting":
                        session.status = "waiting_orchestrator"
            elif (
                not session.reauth_confirm_sent
                and not session.saw_auth_menu
                and not session.saw_auth_url
                and now - session.reauth_requested_at >= _REAUTH_CONFIRM_DELAY_SECONDS
            ):
                # Gemini screen-reader may require an extra Enter after injected slash command.
                self._write_input_locked(session, "\r")
                session.reauth_confirm_sent = True
                session.reauth_confirmed_at = now

    def _extract_checked_option(self, text: str) -> int | None:
        marker_index = text.rfind(_MENU_ANCHOR)
        if marker_index < 0:
            return None
        tail = text[marker_index:]
        match = re.search(r"\(checked\)\s*(\d+)\.", tail)
        if not match:
            return None
        try:
            return int(match.group(1))
        except Exception:
            return None

    def _extract_auth_url(self, text: str) -> str | None:
        marker_index = text.rfind(_URL_ANCHOR)
        if marker_index < 0:
            return None
        tail = text[marker_index + len(_URL_ANCHOR):]
        stop_index = tail.find(_CODE_PROMPT_ANCHOR)
        if stop_index >= 0:
            tail = tail[:stop_index]
        compact = re.sub(r"\s+", "", tail)
        match = _URL_PATTERN.search(compact)
        if not match:
            match = _URL_PATTERN.search(tail)
        if not match:
            return None
        return match.group(0).strip().rstrip(".,);")

    def _build_error_summary_locked(self, session: GeminiAuthCliSession) -> str:
        if not session._line_tail:
            return ""
        return " | ".join(session._line_tail[-3:])

    def _write_input_locked(self, session: GeminiAuthCliSession, text: str) -> None:
        if session.process.poll() is not None:
            return
        try:
            os.write(session.master_fd, text.encode("utf-8", errors="replace"))
        except OSError:
            pass

    def _terminate_process_locked(self, session: GeminiAuthCliSession) -> None:
        proc = session.process
        if proc.poll() is None:
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
        if not session._closed_fd:
            try:
                os.close(session.master_fd)
            except OSError:
                pass
            session._closed_fd = True
