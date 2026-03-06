from __future__ import annotations

from types import SimpleNamespace

import pytest

from server.services.platform import process_termination


def test_terminate_pid_tree_invalid_pid() -> None:
    result = process_termination.terminate_pid_tree(0)
    assert result.outcome == "failed"
    assert result.detail == "invalid_pid"


def test_terminate_pid_tree_returns_already_exited_when_pid_not_alive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_termination, "_is_pid_alive", lambda _pid: False)
    result = process_termination.terminate_pid_tree(12345)
    assert result.outcome == "already_exited"
    assert result.detail == "pid_not_alive"


def test_terminate_pid_tree_windows_taskkill_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process_termination.platform, "system", lambda: "Windows")
    monkeypatch.setattr(process_termination, "_is_pid_alive", lambda _pid: True)
    monkeypatch.setattr(
        process_termination.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )
    result = process_termination.terminate_pid_tree(23456)
    assert result.outcome == "terminated"
    assert result.detail == "taskkill_ok"


@pytest.mark.asyncio
async def test_terminate_asyncio_process_tree_already_exited() -> None:
    proc = SimpleNamespace(returncode=0)
    result = await process_termination.terminate_asyncio_process_tree(proc)  # type: ignore[arg-type]
    assert result.outcome == "already_exited"
    assert result.detail == "returncode_present"


def test_terminate_popen_process_tree_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    proc = SimpleNamespace(pid=123, poll=lambda: None)
    monkeypatch.setattr(
        process_termination,
        "terminate_pid_tree",
        lambda _pid, **_kwargs: process_termination.TerminationResult("terminated", "ok"),
    )
    result = process_termination.terminate_popen_process_tree(proc)  # type: ignore[arg-type]
    assert result.outcome == "terminated"
    assert result.detail == "ok"
