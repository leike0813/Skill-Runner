import os
import time
from datetime import timedelta
from pathlib import Path

from server.engines.iflow.auth.drivers.cli_delegate_flow import (
    IFlowAuthCliFlow,
    IFlowAuthCliSession,
    _utc_now,
)


class _FakeProcess:
    def __init__(self, returncode: int | None = None) -> None:
        self._returncode = returncode
        self.pid = os.getpid()

    def poll(self):
        return self._returncode


def _build_session(tmp_path: Path, master_fd: int) -> IFlowAuthCliSession:
    now = _utc_now()
    return IFlowAuthCliSession(
        session_id="if-1",
        process=_FakeProcess(None),  # type: ignore[arg-type]
        master_fd=master_fd,
        output_path=tmp_path / "iflow_auth.log",
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
    flow = IFlowAuthCliFlow()
    text = """
iFlow OAuth 登录
1. 请复制以下链接并在浏览器中打开：
https://iflow.cn/oauth?loginMethod=phone&type=phone&redirect=https%3A%2F%2Fiflow.cn%2Foauth%2Fcode-display&sta
te=123456&client_id=10009311001
2. 登录您的心流账号并授权
授权码：
"""
    extracted = flow._extract_auth_url(text)
    assert extracted is not None
    assert extracted.startswith("https://iflow.cn/oauth?")
    assert "state=123456" in extracted


def test_menu_checked_option_correction_and_confirm(tmp_path: Path):
    flow = IFlowAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session._clean_buffer = (
            "您希望如何为此项目进行身份验证？\n"
            "  1. 使用 iFlow 登录（推荐）\n"
            "● 2. 使用 API Key\n"
            "（按回车选择）\n"
        )
        flow._consume_output_locked(session)
        sent = _drain_pipe(read_fd)
        assert b"\x1b[A" in sent
        assert session.status == "waiting_orchestrator"

        session._clean_buffer = (
            "您希望如何为此项目进行身份验证？\n"
            "● 1. 使用 iFlow 登录（推荐）\n"
            "  2. 使用 API Key\n"
            "（按回车选择）\n"
        )
        flow._consume_output_locked(session)
        sent = _drain_pipe(read_fd)
        assert b"\r" in sent
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_oauth_submit_model_confirm_and_success(tmp_path: Path):
    flow = IFlowAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session._clean_buffer = (
            "iFlow OAuth 登录\n"
            "1. 请复制以下链接并在浏览器中打开：\n"
            "https://iflow.cn/oauth?loginMethod=phone&type=phone&redirect=https%3A%2F%2Fiflow.cn%2Foauth%2Fcode-display&sta\n"
            "te=123&client_id=10009311001\n"
            "2. 登录您的心流账号并授权\n"
            "授权码：\n"
            "粘贴授权码...\n"
        )
        flow._consume_output_locked(session)
        assert session.status == "waiting_user"
        assert session.auth_url is not None

        flow.submit_code(session, "ABCD1234")
        sent = _drain_pipe(read_fd)
        assert b"ABCD1234\r" in sent
        assert session.status == "code_submitted_waiting_result"

        session._clean_buffer += "模型选择\n按回车使用默认选择：GLM 4.7\n"
        flow._consume_output_locked(session)
        sent = _drain_pipe(read_fd)
        assert b"\r" in sent

        session._clean_buffer += "输入消息或@文件路径\n"
        flow._consume_output_locked(session)
        assert session.status == "succeeded"
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_oauth_url_refresh_resets_submitted_state_and_requires_retry(tmp_path: Path):
    flow = IFlowAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session.code_submitted = True
        session.code_submitted_at = 1.0
        session.auth_url = "https://iflow.cn/oauth?state=old"
        session._clean_buffer = (
            "iFlow OAuth 登录\n"
            "1. 请复制以下链接并在浏览器中打开：\n"
            "https://iflow.cn/oauth?state=new\n"
            "授权码：\n"
            "粘贴授权码...\n"
        )
        flow._consume_output_locked(session)
        assert session.code_submitted is False
        assert session.status == "waiting_user"
        assert session.auth_url == "https://iflow.cn/oauth?state=new"
        assert session.error is not None
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_oauth_submit_timeout_falls_back_to_waiting_user(tmp_path: Path):
    flow = IFlowAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session.code_submitted = True
        session.code_submitted_at = 0.1
        session.auth_url = "https://iflow.cn/oauth?state=abc"
        session._clean_buffer = (
            "iFlow OAuth 登录\n"
            "1. 请复制以下链接并在浏览器中打开：\n"
            "https://iflow.cn/oauth?state=abc\n"
            "授权码：\n"
            "粘贴授权码...\n"
        )
        session.code_submitted_at = time.monotonic() - 99.0
        flow._consume_output_locked(session)
        assert session.code_submitted is False
        assert session.status == "waiting_user"
        assert session.error is not None
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_oauth_submit_stalled_sends_single_extra_enter(tmp_path: Path):
    flow = IFlowAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session.status = "waiting_user"
        flow.submit_code(session, "CODE1234")
        _ = _drain_pipe(read_fd)
        session._clean_buffer = (
            "iFlow OAuth 登录\n"
            "1. 请复制以下链接并在浏览器中打开：\n"
            "https://iflow.cn/oauth?state=abc\n"
            "授权码：\n"
            "粘贴授权码...\n"
        )
        session.code_confirm_last_at = time.monotonic() - 99.0
        flow._consume_output_locked(session)
        sent = _drain_pipe(read_fd)
        assert sent == b"\r"
        assert session.code_confirm_attempts == 1
    finally:
        os.close(read_fd)
        os.close(write_fd)


def test_main_ui_triggers_auth_command_once(tmp_path: Path):
    flow = IFlowAuthCliFlow()
    read_fd, write_fd = os.pipe()
    try:
        session = _build_session(tmp_path, write_fd)
        session._clean_buffer = "输入消息或@文件路径\n"
        flow._consume_output_locked(session)
        before_delay = _drain_pipe(read_fd)
        assert before_delay == b""
        assert session.reauth_requested is False

        session.main_ui_seen_at = 0.0
        flow.refresh(session)
        _ = _drain_pipe(read_fd)

        session.main_ui_seen_at = session.main_ui_seen_at - 10.0
        flow.refresh(session)
        sent = _drain_pipe(read_fd)
        assert b"/auth\r" in sent
        assert session.reauth_requested is True

        session.reauth_requested_at = 0.0
        flow.refresh(session)
        sent = _drain_pipe(read_fd)
        assert sent == b"\r"
        assert session.reauth_confirm_sent is True
    finally:
        os.close(read_fd)
        os.close(write_fd)
