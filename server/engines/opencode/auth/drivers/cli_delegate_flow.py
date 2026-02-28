from __future__ import annotations

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

_PROVIDER_MENU_ANCHOR = "Select provider"
_LOGIN_METHOD_ANCHOR = "Login method"
_GOOGLE_ACCOUNT_ANCHOR = "Google accounts (Antigravity)"
_PROJECT_ID_ANCHOR = "Project ID"
_OAUTH_URL_ANCHOR = "OAuth URL:"
_REDIRECT_PROMPT_ANCHOR = "Paste the redirect URL (or just the code) here:"
_ADD_ANOTHER_ACCOUNT_ANCHOR = "Add another account?"
_OPENAI_GO_TO_ANCHOR = "Go to:"
_OPENAI_WAITING_ANCHOR = "Waiting for authorization"
_OPENAI_COMPLETE_IN_BROWSER_ANCHOR = "Complete authorization in your browser"
_ACTION_COOLDOWN_SECONDS = 0.7
_DEVICE_CODE_PATTERN = re.compile(r"\b[A-Z0-9]{4}(?:-[A-Z0-9]{4,})+\b")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _strip_ansi(text: str) -> str:
    cleaned = _ANSI_OSC_PATTERN.sub("", text)
    cleaned = _ANSI_CSI_PATTERN.sub("", cleaned)
    return cleaned


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


@dataclass
class OpencodeAuthCliSession:
    session_id: str
    process: subprocess.Popen[Any]
    master_fd: int
    output_path: Path
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    provider_id: str
    provider_label: str
    openai_auth_method: str = "callback"
    status: str = "starting"
    auth_url: str | None = None
    user_code: str | None = None
    error: str | None = None
    exit_code: int | None = None
    input_submitted: bool = False
    provider_selected: bool = False
    method_selected: bool = False
    account_menu_selected: bool = False
    project_id_submitted: bool = False
    add_another_account_declined: bool = False
    _closed_fd: bool = False
    _clean_buffer: str = ""
    _line_tail: list[str] = field(default_factory=list)
    _reader_thread: Thread | None = None
    _last_action_at: float = 0.0
    _lock: Lock = field(default_factory=Lock, repr=False)


class OpencodeAuthCliFlow:
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
        provider_label: str,
        openai_auth_method: str = "callback",
    ) -> OpencodeAuthCliSession:
        master_fd, slave_fd = pty.openpty()
        try:
            process = subprocess.Popen(
                [str(command_path), "auth", "login"],
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
        session = OpencodeAuthCliSession(
            session_id=session_id,
            process=process,
            master_fd=master_fd,
            output_path=output_path,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
            provider_id=provider_id,
            provider_label=provider_label,
            openai_auth_method=openai_auth_method,
        )
        reader = Thread(target=self._reader_loop, args=(session,), daemon=True)
        session._reader_thread = reader
        reader.start()
        return session

    def refresh(self, session: OpencodeAuthCliSession) -> None:
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
            session.error = summary or f"opencode auth exited with code {rc}"

    def submit_input(self, session: OpencodeAuthCliSession, value: str) -> None:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Input value is required")
        with session._lock:
            if session.status in _TERMINAL_STATUSES:
                raise ValueError("Auth session already finished")
            if session.status not in {"waiting_user", "code_submitted_waiting_result"}:
                raise ValueError("OpenCode auth session is not waiting for user input")
            self._write_input_locked(session, normalized + "\r")
            session.input_submitted = True
            session.status = "code_submitted_waiting_result"
            session.error = None
            session.updated_at = _utc_now()

    def cancel(self, session: OpencodeAuthCliSession) -> None:
        with session._lock:
            if session.status in _TERMINAL_STATUSES:
                return
            self._terminate_process_locked(session)
            session.status = "canceled"
            session.error = session.error or "Canceled by user"
            session.updated_at = _utc_now()

    def _reader_loop(self, session: OpencodeAuthCliSession) -> None:
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

    def _append_output_locked(self, session: OpencodeAuthCliSession, chunk: str) -> None:
        try:
            with session.output_path.open("a", encoding="utf-8") as stream:
                stream.write(chunk)
        except Exception:
            pass

        cleaned = _strip_ansi(chunk).replace("\r", "\n")
        session._clean_buffer = (session._clean_buffer + cleaned)[-30000:]
        for row in cleaned.splitlines():
            line = row.strip()
            if not line:
                continue
            session._line_tail.append(line)
            if len(session._line_tail) > 30:
                session._line_tail = session._line_tail[-30:]

    def _consume_output_locked(self, session: OpencodeAuthCliSession) -> None:
        if session.status in _TERMINAL_STATUSES:
            return
        window = session._clean_buffer
        compact = _compact_text(window)

        auth_url = self._extract_auth_url(window)
        if not auth_url:
            auth_url = self._extract_generic_auth_url(window)
        if auth_url:
            session.auth_url = auth_url
        user_code = self._extract_user_code(window)
        if user_code:
            session.user_code = user_code

        if _compact_text(_REDIRECT_PROMPT_ANCHOR) in compact:
            if not session.input_submitted:
                session.status = "waiting_user"
                return
            session.status = "code_submitted_waiting_result"

        if (
            session.provider_id == "google"
            and session.input_submitted
            and not session.add_another_account_declined
            and _compact_text(_ADD_ANOTHER_ACCOUNT_ANCHOR) in compact
        ):
            if self._can_take_action(session):
                self._write_input_locked(session, "n\r")
                session.add_another_account_declined = True
                session.status = "waiting_orchestrator"
                session._last_action_at = time.monotonic()
            return

        if session.provider_id == "openai" and (
            _compact_text(_OPENAI_WAITING_ANCHOR) in compact
            or _compact_text(_OPENAI_COMPLETE_IN_BROWSER_ANCHOR) in compact
        ):
            # OpenAI browser OAuth flow does not require redirect/code input in terminal.
            # URL parsing can be affected by transient TUI rendering noise, so we enter
            # waiting_user as soon as the stable waiting anchors appear.
            session.status = "waiting_user"
            return

        if session.input_submitted and self._is_success_output(compact):
            session.status = "succeeded"
            session.error = None
            return

        if _compact_text(_PROVIDER_MENU_ANCHOR) in compact and not session.provider_selected:
            if self._can_take_action(session):
                self._select_provider_locked(session, window)
                session.provider_selected = True
                session.status = "waiting_orchestrator"
            return

        if _compact_text(_LOGIN_METHOD_ANCHOR) in compact and not session.method_selected:
            if self._can_take_action(session):
                self._select_login_method_locked(session, window)
                session.method_selected = True
                session.status = "waiting_orchestrator"
            return

        if (
            session.provider_id == "google"
            and _compact_text(_GOOGLE_ACCOUNT_ANCHOR) in compact
            and not session.account_menu_selected
        ):
            if self._can_take_action(session):
                self._select_option_by_label_locked(
                    session,
                    window,
                    target_keywords=["add account"],
                    fallback_index=1,
                )
                session.account_menu_selected = True
                session.status = "waiting_orchestrator"
            return

        if (
            session.provider_id == "google"
            and _compact_text(_PROJECT_ID_ANCHOR) in compact
            and not session.project_id_submitted
        ):
            if self._can_take_action(session):
                self._write_input_locked(session, "\r")
                session.project_id_submitted = True
                session.status = "waiting_orchestrator"
                session._last_action_at = time.monotonic()
            return

    def _extract_menu_options(self, text: str) -> tuple[int | None, list[str]]:
        selected: int | None = None
        options: list[str] = []
        for line in text.splitlines():
            row = line.strip()
            if not row:
                continue
            if row.startswith("●"):
                options.append(row[1:].strip())
                selected = len(options)
                continue
            if row.startswith("○"):
                options.append(row[1:].strip())
        return selected, options

    def _provider_fallback_index(self, provider_id: str) -> int:
        if provider_id == "openai":
            return 4
        if provider_id == "google":
            return 5
        return 1

    def _select_provider_locked(self, session: OpencodeAuthCliSession, text: str) -> None:
        self._select_option_by_label_locked(
            session,
            text,
            target_keywords=[session.provider_label.lower()],
            fallback_index=self._provider_fallback_index(session.provider_id),
        )

    def _select_login_method_locked(self, session: OpencodeAuthCliSession, text: str) -> None:
        if session.provider_id == "openai":
            if session.openai_auth_method == "auth_code_or_url":
                keywords = ["headless"]
                fallback_index = 2
            else:
                keywords = ["browser"]
                fallback_index = 1
        elif session.provider_id == "google":
            keywords = ["oauth", "google"]
            fallback_index = 1
        else:
            keywords = ["oauth"]
            fallback_index = 1
        self._select_option_by_label_locked(
            session,
            text,
            target_keywords=keywords,
            fallback_index=fallback_index,
        )

    def _select_option_by_label_locked(
        self,
        session: OpencodeAuthCliSession,
        text: str,
        *,
        target_keywords: list[str],
        fallback_index: int,
    ) -> None:
        selected, options = self._extract_menu_options(text)
        target_index: int | None = None
        lowered_keywords = [item.strip().lower() for item in target_keywords if item.strip()]
        if options:
            for idx, option in enumerate(options, start=1):
                lower = option.lower()
                if all(keyword in lower for keyword in lowered_keywords):
                    target_index = idx
                    break
        if target_index is None:
            target_index = max(1, fallback_index)

        if selected is None:
            selected = 1
        diff = target_index - selected
        if diff < 0:
            self._write_input_locked(session, "\x1b[A" * abs(diff))
        elif diff > 0:
            self._write_input_locked(session, "\x1b[B" * diff)
        self._write_input_locked(session, "\r")
        session._last_action_at = time.monotonic()

    def _can_take_action(self, session: OpencodeAuthCliSession) -> bool:
        return time.monotonic() - session._last_action_at >= _ACTION_COOLDOWN_SECONDS

    def _extract_auth_url(self, text: str) -> str | None:
        marker_idx = text.rfind(_OAUTH_URL_ANCHOR)
        if marker_idx < 0:
            return None
        tail = text[marker_idx + len(_OAUTH_URL_ANCHOR):]
        stop_idx = tail.find(_REDIRECT_PROMPT_ANCHOR)
        if stop_idx >= 0:
            tail = tail[:stop_idx]
        # Prefer raw-text match first to avoid accidentally concatenating guidance
        # text into the URL when logs contain multiline instructions.
        match = _URL_PATTERN.search(tail)
        if match:
            return match.group(0).strip().rstrip(".,);")

        compact = re.sub(r"\s+", "", tail)
        match = _URL_PATTERN.search(compact)
        if not match:
            return None
        candidate = match.group(0).strip().rstrip(".,);")
        lowered = candidate.lower()
        cut_markers = (
            "couldnotopenbrowserautomatically",
            "pleaseopentheurlabovemanually",
            "1.opentheurlabove",
            "2.afterapproving",
            "3.pasteitbackhere",
        )
        for marker in cut_markers:
            idx = lowered.find(marker)
            if idx > 0:
                candidate = candidate[:idx]
                break
        return candidate.rstrip(".,);")

    def _extract_generic_auth_url(self, text: str) -> str | None:
        marker_idx = text.rfind(_OPENAI_GO_TO_ANCHOR)
        if marker_idx >= 0:
            tail = text[marker_idx + len(_OPENAI_GO_TO_ANCHOR):]
            match = _URL_PATTERN.search(tail)
            if match:
                return match.group(0).strip().rstrip(".,);")
        matches = _URL_PATTERN.findall(text)
        if not matches:
            return None
        return matches[-1].strip().rstrip(".,);")

    def _extract_user_code(self, text: str) -> str | None:
        cleaned = _strip_ansi(text)
        for line in cleaned.splitlines():
            lowered = line.lower()
            if "code" not in lowered and "one-time" not in lowered and "device" not in lowered:
                continue
            match = _DEVICE_CODE_PATTERN.search(line.upper())
            if match:
                return match.group(0)
        match = _DEVICE_CODE_PATTERN.search(cleaned.upper())
        if match:
            return match.group(0)
        return None

    def _is_success_output(self, compact: str) -> bool:
        anchors = (
            "loginsuccessful",
            "authenticated",
            "credentialsaved",
            "addedaccount",
            "accountadded",
            "successfully",
        )
        return any(anchor in compact for anchor in anchors)

    def _build_error_summary_locked(self, session: OpencodeAuthCliSession) -> str:
        if not session._line_tail:
            return ""
        return " | ".join(session._line_tail[-3:])

    def _write_input_locked(self, session: OpencodeAuthCliSession, text: str) -> None:
        if session.process.poll() is not None:
            return
        try:
            os.write(session.master_fd, text.encode("utf-8", errors="replace"))
        except OSError:
            pass

    def _terminate_process_locked(self, session: OpencodeAuthCliSession) -> None:
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
