import os
import time
from datetime import timedelta
from pathlib import Path

from server.services.gemini_auth_cli_flow import GeminiAuthCliFlow, GeminiAuthCliSession, _utc_now


class _FakeProcess:
    def __init__(self, returncode: int | None = None) -> None:
        self._returncode = returncode
        self.pid = os.getpid()

    def poll(self):
        return self._returncode


def _build_session(tmp_path: Path, master_fd: int) -> GeminiAuthCliSession:
    now = _utc_now()
    return GeminiAuthCliSession(
        session_id="g-1",
        process=_FakeProcess(None),  # type: ignore[arg-type]
        master_fd=master_fd,
        output_path=tmp_path / "gemini_auth.log",
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=5),
    )


def _drain_pipe(read_fd: int) -> bytes:
    os.set_blocking(read_fd, False)
    chunks: list[bytes] = []
    while True:
        try:
            chunk = os.read(read_fd, 4096)
        except BlockingIOError:
            break
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def test_extract_auth_url_multiline_compaction():
    flow = GeminiAuthCliFlow()
    text = """
Please visit the following URL to authorize the application:

https://accounts.google.com/o/oauth2/v2/auth?redirect_uri=https%3A%2F%2Fcodeassist.google.com%2Fauthcode&access_type=off
line&scope=openid

Enter the authorization code:
"""
    extracted = flow._extract_auth_url(text)
    assert extracted is not None
    assert extracted.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "offline" in extracted


def test_consume_output_state_transitions(tmp_path: Path):
    flow = GeminiAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session._clean_buffer = (
            "How would you like to authenticate for this project?\n"
            "(checked) 1. Login with Google\n"
            "(Use Enter to select)\n"
        )
        flow._consume_output_locked(session)
        assert session.status == "waiting_orchestrator"
        assert session.menu_entered_at > 0

        session._clean_buffer += (
            "Please visit the following URL to authorize the application:\n\n"
            "https://accounts.google.com/o/oauth2/v2/auth?client_id=abc\n\n"
            "Enter the authorization code:\n"
        )
        flow._consume_output_locked(session)
        assert session.status == "waiting_user"
        assert session.auth_url == "https://accounts.google.com/o/oauth2/v2/auth?client_id=abc"

        session.code_submitted = True
        session._clean_buffer += "Type your message or @path/to/file\n"
        flow._consume_output_locked(session)
        assert session.status == "succeeded"
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_consume_output_menu_checked_api_key_switches_to_google(tmp_path: Path):
    flow = GeminiAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session._clean_buffer = (
            "How would you like to authenticate for this project?\n"
            "1. Login with Google\n"
            "(checked) 2. Use Gemini API Key\n"
            "3. Vertex AI\n"
            "(Use Enter to select)\n"
        )
        flow._consume_output_locked(session)
        sent = _drain_pipe(read_fd)
        assert b"\x1b[A" in sent
        assert session.status == "waiting_orchestrator"

        session._clean_buffer = (
            "How would you like to authenticate for this project?\n"
            "(checked) 1. Login with Google\n"
            "2. Use Gemini API Key\n"
            "3. Vertex AI\n"
            "(Use Enter to select)\n"
        )
        flow._consume_output_locked(session)
        sent = _drain_pipe(read_fd)
        assert b"\r" in sent
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_consume_output_api_key_prompt_sends_escape(tmp_path: Path):
    flow = GeminiAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session._clean_buffer = (
            "Enter Gemini API Key\n"
            "Please enter your Gemini API key.\n"
            "Paste your API key here\n"
            "(Press Enter to submit, Esc to cancel, Ctrl+C to clear stored key)\n"
        )
        flow._consume_output_locked(session)
        sent = _drain_pipe(read_fd)
        assert b"\x1b" in sent
        assert session.status == "starting"
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_consume_output_reauth_waits_and_sends_single_confirm_enter(tmp_path: Path):
    flow = GeminiAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session._clean_buffer = "Type your message or @path/to/file\n"
        flow._consume_output_locked(session)
        first = _drain_pipe(read_fd)
        assert first == b""
        assert session.main_ui_seen_at > 0.0
        assert session.reauth_attempts == 0

        session.main_ui_seen_at = time.monotonic() - 10.0
        flow.refresh(session)
        inject = _drain_pipe(read_fd)
        assert b"/auth\r" in inject
        assert session.reauth_attempts == 1

        # No auth menu/url seen; refresh should send a single confirm Enter,
        # but still must not reinject /auth command.
        session.reauth_requested_at = 0.0
        flow.refresh(session)
        second = _drain_pipe(read_fd)
        assert second == b"\r"
        assert session.reauth_confirm_sent is True
        assert session.reauth_attempts == 1
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_consume_output_reauth_triggers_only_after_main_ui_anchor(tmp_path: Path):
    flow = GeminiAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session._clean_buffer = "Logged in with Google: demo@example.com  /auth\n"
        flow._consume_output_locked(session)
        before_main_ui = _drain_pipe(read_fd)
        assert before_main_ui == b""
        assert session.reauth_attempts == 0

        session._clean_buffer += "Type your message or @path/to/file\n"
        flow._consume_output_locked(session)
        after_main_ui = _drain_pipe(read_fd)
        assert after_main_ui == b""
        assert session.reauth_attempts == 0
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_consume_output_menu_navigation_fallback_submits_enter(tmp_path: Path):
    flow = GeminiAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session._clean_buffer = (
            "How would you like to authenticate for this project?\n"
            "1. Login with Google\n"
            "(checked) 3. Vertex AI\n"
            "(Use Enter to select)\n"
        )
        flow._consume_output_locked(session)
        _ = _drain_pipe(read_fd)
        # Simulate clock progression without buffer repaint.
        session.menu_navigated_at = 0.0
        session.menu_entered_at = 0.0
        flow.refresh(session)
        sent = _drain_pipe(read_fd)
        assert b"\r" in sent
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_consume_output_trust_prompt_auto_enter(tmp_path: Path):
    flow = GeminiAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session._clean_buffer = (
            "/home/demo no sandbox /model Auto (Gemini 3)\n"
            "Do you trust this folder?\n"
            "(checked) 1. Trust folder (demo)\n"
        )
        flow._consume_output_locked(session)
        assert session.status == "starting"
        assert session.trust_prompt_entered_at > 0
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_consume_output_main_ui_alt_anchor_does_not_trigger_reauth(tmp_path: Path):
    flow = GeminiAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session._clean_buffer = "? for shortcuts\n"
        flow._consume_output_locked(session)
        sent = _drain_pipe(read_fd)
        assert sent == b""
        assert session.reauth_attempts == 0
        assert session.status == "starting"
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_submit_code_requires_waiting_state(tmp_path: Path):
    flow = GeminiAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session.status = "waiting_user"
        flow.submit_code(session, "ABCD-EFGH")
        assert session.status == "code_submitted_waiting_result"
        assert session.code_submitted is True
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_consume_output_code_prompt_blocks_further_auto_input(tmp_path: Path):
    flow = GeminiAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session.reauth_requested = True
        session.reauth_requested_at = 0.0
        session._clean_buffer = (
            "Type your message or @path/to/file\n"
            "How would you like to authenticate for this project?\n"
            "(checked) 1. Login with Google\n"
            "(Use Enter to select)\n"
            "Please visit the following URL to authorize the application:\n"
            "https://accounts.google.com/o/oauth2/v2/auth?client_id=abc\n"
            "Enter the authorization code:\n"
        )
        flow._consume_output_locked(session)
        sent = _drain_pipe(read_fd)
        assert sent == b""
        assert session.status == "waiting_user"
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_consume_output_direct_url_stage_short_circuits_automation(tmp_path: Path):
    flow = GeminiAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session._clean_buffer = (
            "Enter Gemini API Key\n"
            "Paste your API key here\n"
            "(Press Enter to submit, Esc to cancel, Ctrl+C to clear stored key)\n"
            "Please visit the following URL to authorize the application:\n"
            "https://accounts.google.com/o/oauth2/v2/auth?client_id=abc\n"
            "Enter the authorization code:\n"
        )
        flow._consume_output_locked(session)
        sent = _drain_pipe(read_fd)
        assert sent == b""
        assert session.status == "waiting_user"
        assert session.auth_url == "https://accounts.google.com/o/oauth2/v2/auth?client_id=abc"
        assert session.saw_auth_url is True
    finally:
        os.close(read_fd)
        os.close(write_fd)
