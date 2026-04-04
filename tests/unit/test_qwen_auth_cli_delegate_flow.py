from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from server.engines.qwen.auth.drivers.cli_delegate_flow import (
    QwenAuthCliFlow,
    QwenAuthCliSession,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _FakeProcess:
    def __init__(self, return_code=None) -> None:
        self._return_code = return_code
        self.pid = 4321

    def poll(self):  # noqa: ANN201
        return self._return_code


def _build_session(tmp_path: Path, *, provider_id: str) -> QwenAuthCliSession:
    now = _utc_now()
    return QwenAuthCliSession(
        session_id="auth-qwen-1",
        provider_id=provider_id,
        process=_FakeProcess(),
        master_fd=0,
        output_path=tmp_path / "auth.log",
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=5),
    )


def test_qwen_cli_delegate_flow_extracts_qwen_oauth_url(tmp_path: Path) -> None:
    flow = QwenAuthCliFlow(tmp_path / "agent_home")
    session = _build_session(tmp_path, provider_id="qwen-oauth")

    flow._append_output_locked(  # noqa: SLF001
        session,
        """
        Starting Qwen OAuth authentication...
        Please visit the following URL in your browser to authorize:
        https://chat.qwen.ai/device?user_code=TEST123
        Waiting for authorization...
        """,
    )
    flow._consume_output_locked(session)  # noqa: SLF001

    assert session.status == "waiting_user"
    assert session.auth_url == "https://chat.qwen.ai/device?user_code=TEST123"
    assert session.user_code == "TEST123"


def test_qwen_cli_delegate_flow_coding_plan_region_and_api_key_prompt(tmp_path: Path) -> None:
    flow = QwenAuthCliFlow(tmp_path / "agent_home")
    session = _build_session(tmp_path, provider_id="coding-plan-global")
    writes: list[str] = []
    flow._write_input_locked = lambda _session, text: writes.append(text)  # type: ignore[method-assign]  # noqa: SLF001

    flow._append_output_locked(session, "Select region for Coding Plan:\n")
    flow._consume_output_locked(session)  # noqa: SLF001
    assert session.status == "waiting_orchestrator"
    assert session.region_selected is True
    assert writes == ["\x1b[B", "\r"]

    flow._append_output_locked(session, "Enter your Coding Plan API key: ")
    flow._consume_output_locked(session)  # noqa: SLF001
    assert session.status == "waiting_user"
    assert session.api_key_prompt_visible is True

    flow.submit_api_key(session, "sk-sp-123")
    assert session.status == "code_submitted_waiting_result"
    assert writes[-1] == "sk-sp-123\r"


def test_qwen_cli_delegate_flow_refresh_marks_success_after_exit(tmp_path: Path) -> None:
    flow = QwenAuthCliFlow(tmp_path / "agent_home")
    session = _build_session(tmp_path, provider_id="coding-plan-china")
    session.process = _FakeProcess(return_code=0)
    flow._append_output_locked(session, "Successfully authenticated with Alibaba Cloud Coding Plan.\n")

    flow.refresh(session)

    assert session.status == "succeeded"
    assert session.error is None
