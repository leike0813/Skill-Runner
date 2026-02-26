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

_MAIN_UI_ANCHOR = "输入消息或@文件路径"
_AUTH_MENU_ANCHOR = "您希望如何为此项目进行身份验证？"
_AUTH_MENU_ENTER_HINT = "（按回车选择）"
_AUTH_MENU_SELECTED_PATTERN = re.compile(r"●\s*(\d+)\.")
_OAUTH_TITLE_ANCHOR = "iFlow OAuth 登录"
_OAUTH_URL_STEP_ANCHOR = "1. 请复制以下链接并在浏览器中打开："
_OAUTH_STEP2_ANCHOR = "2. 登录您的心流账号并授权"
_OAUTH_CODE_LABEL_ANCHOR = "授权码："
_OAUTH_CODE_INPUT_ANCHOR = "粘贴授权码"
_MODEL_SELECT_ANCHOR = "模型选择"
_MODEL_DEFAULT_HINT_ANCHOR = "按回车使用默认选择"

_MENU_ACTION_COOLDOWN_SECONDS = 0.6
_AUTH_INITIAL_DELAY_SECONDS = 1.5
_AUTH_CONFIRM_DELAY_SECONDS = 2.0
_MODEL_CONFIRM_COOLDOWN_SECONDS = 0.8
_CODE_RESULT_TIMEOUT_SECONDS = 8.0
_CODE_CONFIRM_RETRY_DELAY_SECONDS = 1.5
_CODE_CONFIRM_MAX_RETRIES = 1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _strip_ansi(text: str) -> str:
    cleaned = _ANSI_OSC_PATTERN.sub("", text)
    cleaned = _ANSI_CSI_PATTERN.sub("", cleaned)
    return cleaned


@dataclass
class IFlowAuthCliSession:
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
    reauth_confirm_sent: bool = False
    reauth_confirmed_at: float = 0.0
    main_ui_seen_at: float = 0.0
    menu_selection_confirmed: bool = False
    menu_last_checked_option: int | None = None
    menu_navigated_at: float = 0.0
    menu_entered_at: float = 0.0
    saw_auth_menu: bool = False
    saw_auth_url: bool = False
    code_submitted: bool = False
    code_submitted_at: float = 0.0
    code_confirm_attempts: int = 0
    code_confirm_last_at: float = 0.0
    model_confirm_sent: bool = False
    model_confirmed_at: float = 0.0
    saw_output: bool = False
    _closed_fd: bool = False
    _clean_buffer: str = ""
    _line_tail: list[str] = field(default_factory=list)
    _reader_thread: Thread | None = None
    _lock: Lock = field(default_factory=Lock, repr=False)


class IFlowAuthCliFlow:
    def start_session(
        self,
        *,
        session_id: str,
        command_path: Path,
        cwd: Path,
        env: dict[str, str],
        output_path: Path,
        expires_at: datetime,
    ) -> IFlowAuthCliSession:
        master_fd, slave_fd = pty.openpty()
        try:
            process = subprocess.Popen(
                [str(command_path)],
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
        session = IFlowAuthCliSession(
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

    def refresh(self, session: IFlowAuthCliSession) -> None:
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
            session.error = summary or f"iflow auth exited with code {rc}"

    def submit_code(self, session: IFlowAuthCliSession, code: str) -> None:
        normalized = code.strip()
        if not normalized:
            raise ValueError("Authorization code is required")
        with session._lock:
            if session.status in _TERMINAL_STATUSES:
                raise ValueError("Auth session already finished")
            if session.status not in {"waiting_user", "code_submitted_waiting_result"}:
                raise ValueError("iFlow auth session is not waiting for authorization code")
            # Use plain input + Enter for broad PTY compatibility.
            self._write_input_locked(session, normalized + "\r")
            session.code_submitted = True
            now = time.monotonic()
            session.code_submitted_at = now
            session.code_confirm_attempts = 0
            session.code_confirm_last_at = now
            session.model_confirm_sent = False
            session.status = "code_submitted_waiting_result"
            session.error = None
            session.updated_at = _utc_now()

    def cancel(self, session: IFlowAuthCliSession) -> None:
        with session._lock:
            if session.status in _TERMINAL_STATUSES:
                return
            self._terminate_process_locked(session)
            session.status = "canceled"
            session.error = session.error or "Canceled by user"
            session.updated_at = _utc_now()

    def _reader_loop(self, session: IFlowAuthCliSession) -> None:
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

    def _append_output_locked(self, session: IFlowAuthCliSession, chunk: str) -> None:
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

    def _consume_output_locked(self, session: IFlowAuthCliSession) -> None:
        if session.status in _TERMINAL_STATUSES:
            return
        window = session._clean_buffer
        main_idx = window.rfind(_MAIN_UI_ANCHOR)
        menu_idx = window.rfind(_AUTH_MENU_ANCHOR)
        oauth_idx = window.rfind(_OAUTH_TITLE_ANCHOR)
        model_idx = window.rfind(_MODEL_SELECT_ANCHOR)
        latest_stage_idx = max(main_idx, menu_idx, oauth_idx, model_idx)
        main_visible = main_idx >= 0 and main_idx == latest_stage_idx
        menu_visible = menu_idx >= 0 and menu_idx == latest_stage_idx
        oauth_visible = oauth_idx >= 0 and oauth_idx == latest_stage_idx
        model_visible = model_idx >= 0 and model_idx == latest_stage_idx

        if oauth_visible:
            previous_auth_url = session.auth_url
            auth_url = self._extract_auth_url(window)
            if auth_url and auth_url != session.auth_url:
                session.auth_url = auth_url
                session.saw_auth_url = True
                if session.code_submitted and previous_auth_url:
                    # New OAuth URL after code submission means previous code flow
                    # has been invalidated and user must retry with fresh code.
                    session.code_submitted = False
                    session.code_submitted_at = 0.0
                    session.model_confirm_sent = False
                    session.status = "waiting_user"
                    session.error = "授权码未通过，请使用新链接重新获取并提交。"
                    return
            elif auth_url:
                session.saw_auth_url = True
            if session.code_submitted:
                now = time.monotonic()
                if (
                    session.code_confirm_attempts < _CODE_CONFIRM_MAX_RETRIES
                    and now - session.code_confirm_last_at >= _CODE_CONFIRM_RETRY_DELAY_SECONDS
                ):
                    # Some iFlow builds keep code in input box without committing.
                    # Send a single extra Enter as a safe retry.
                    self._write_input_locked(session, "\r")
                    session.code_confirm_attempts += 1
                    session.code_confirm_last_at = now
                if (
                    session.code_submitted_at > 0.0
                    and now - session.code_submitted_at >= _CODE_RESULT_TIMEOUT_SECONDS
                ):
                    session.code_submitted = False
                    session.code_submitted_at = 0.0
                    session.code_confirm_attempts = 0
                    session.code_confirm_last_at = 0.0
                    session.model_confirm_sent = False
                    session.status = "waiting_user"
                    session.error = "授权码校验超时，请重新获取并提交授权码。"
                    return
                session.status = "code_submitted_waiting_result"
            else:
                session.status = "waiting_user"
            return

        if model_visible:
            if session.code_submitted:
                now = time.monotonic()
                if (
                    not session.model_confirm_sent
                    and now - session.model_confirmed_at >= _MODEL_CONFIRM_COOLDOWN_SECONDS
                ):
                    self._write_input_locked(session, "\r")
                    session.model_confirm_sent = True
                    session.model_confirmed_at = now
                session.status = "code_submitted_waiting_result"
                session.error = None
            else:
                session.status = "waiting_orchestrator"
            return

        if menu_visible and _AUTH_MENU_ENTER_HINT in window and not session.saw_auth_url:
            session.saw_auth_menu = True
            session.status = "waiting_orchestrator"
            now = time.monotonic()
            checked = self._extract_checked_option(window)
            if checked is not None and checked > 1:
                if now - session.menu_navigated_at >= _MENU_ACTION_COOLDOWN_SECONDS:
                    self._write_input_locked(session, "\x1b[A" * (checked - 1))
                    session.menu_navigated_at = now
                    session.menu_last_checked_option = checked
                    session.menu_selection_confirmed = False
                return

            if (
                not session.menu_selection_confirmed
                and now - session.menu_entered_at >= _MENU_ACTION_COOLDOWN_SECONDS
            ):
                self._write_input_locked(session, "\r")
                session.menu_entered_at = now
                session.menu_last_checked_option = checked
                session.menu_selection_confirmed = True
            return

        if main_visible:
            if session.code_submitted:
                session.status = "succeeded"
                session.error = None
                return
            if session.saw_auth_url:
                # OAuth flow already started; do not trigger a new /auth cycle
                # if TUI briefly redraws back to main layout.
                return
            now = time.monotonic()
            if session.main_ui_seen_at <= 0.0:
                session.main_ui_seen_at = now
            if not session.reauth_requested and now - session.main_ui_seen_at >= _AUTH_INITIAL_DELAY_SECONDS:
                self._write_input_locked(session, "/auth\r")
                session.reauth_requested = True
                session.reauth_requested_at = now
                session.status = "waiting_orchestrator"
                return
            if (
                session.reauth_requested
                and not session.reauth_confirm_sent
                and not session.saw_auth_menu
                and not session.saw_auth_url
                and now - session.reauth_requested_at >= _AUTH_CONFIRM_DELAY_SECONDS
            ):
                # iFlow occasionally keeps /auth in input line without executing.
                # Send a single extra Enter as confirm, but do not re-inject /auth.
                self._write_input_locked(session, "\r")
                session.reauth_confirm_sent = True
                session.reauth_confirmed_at = now
                session.status = "waiting_orchestrator"
            return

    def _extract_checked_option(self, text: str) -> int | None:
        marker_index = text.rfind(_AUTH_MENU_ANCHOR)
        if marker_index < 0:
            return None
        tail = text[marker_index:]
        match = _AUTH_MENU_SELECTED_PATTERN.search(tail)
        if not match:
            return None
        try:
            return int(match.group(1))
        except Exception:
            return None

    def _extract_auth_url(self, text: str) -> str | None:
        marker_index = text.rfind(_OAUTH_URL_STEP_ANCHOR)
        if marker_index >= 0:
            tail = text[marker_index + len(_OAUTH_URL_STEP_ANCHOR):]
        else:
            title_index = text.rfind(_OAUTH_TITLE_ANCHOR)
            if title_index < 0:
                return None
            tail = text[title_index + len(_OAUTH_TITLE_ANCHOR):]
        for stop_anchor in (_OAUTH_STEP2_ANCHOR, _OAUTH_CODE_LABEL_ANCHOR, _OAUTH_CODE_INPUT_ANCHOR):
            stop_index = tail.find(stop_anchor)
            if stop_index >= 0:
                tail = tail[:stop_index]
                break
        compact = re.sub(r"\s+", "", tail)
        match = _URL_PATTERN.search(compact)
        if not match:
            match = _URL_PATTERN.search(tail)
        if not match:
            return None
        return match.group(0).strip().rstrip(".,);")

    def _build_error_summary_locked(self, session: IFlowAuthCliSession) -> str:
        if not session._line_tail:
            return ""
        return " | ".join(session._line_tail[-3:])

    def _write_input_locked(self, session: IFlowAuthCliSession, text: str) -> None:
        if session.process.poll() is not None:
            return
        try:
            os.write(session.master_fd, text.encode("utf-8", errors="replace"))
        except OSError:
            pass

    def _terminate_process_locked(self, session: IFlowAuthCliSession) -> None:
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
