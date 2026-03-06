from __future__ import annotations

from pathlib import Path

import pytest

from server.config import config
from server.services.platform.process_lease_store import ProcessLeaseStore
from server.services.platform.process_supervisor import RuntimeProcessSupervisor
from server.services.platform.process_termination import TerminationResult


class _FakePopenProcess:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self._returncode: int | None = None

    def poll(self) -> int | None:
        return self._returncode


@pytest.fixture
def _enable_supervisor() -> bool:
    previous = bool(config.SYSTEM.PROCESS_SUPERVISOR_ENABLED)
    config.defrost()
    config.SYSTEM.PROCESS_SUPERVISOR_ENABLED = True
    config.freeze()
    return previous


@pytest.fixture(autouse=True)
def _restore_supervisor(_enable_supervisor: bool):
    yield
    config.defrost()
    config.SYSTEM.PROCESS_SUPERVISOR_ENABLED = _enable_supervisor
    config.freeze()


def test_process_supervisor_register_release_is_idempotent(tmp_path: Path) -> None:
    store = ProcessLeaseStore(tmp_path / "runs.db")
    supervisor = RuntimeProcessSupervisor(lease_store=store)
    proc = _FakePopenProcess(12345)

    lease_id = supervisor.register_popen_process(
        owner_kind="ui_shell",
        owner_id="session-1",
        process=proc,  # type: ignore[arg-type]
        engine="codex",
    )
    assert isinstance(lease_id, str) and lease_id
    lease = store.get(lease_id)
    assert isinstance(lease, dict)
    assert lease["status"] == "active"

    supervisor.release(lease_id, reason="done")
    closed = store.get(lease_id)
    assert isinstance(closed, dict)
    assert closed["status"] == "closed"
    assert closed["close_reason"] == "done"

    supervisor.release(lease_id, reason="done_again")
    closed_again = store.get(lease_id)
    assert isinstance(closed_again, dict)
    assert closed_again["status"] == "closed"


@pytest.mark.asyncio
async def test_reap_orphan_leases_on_startup_only_processes_active(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = ProcessLeaseStore(tmp_path / "runs.db")
    supervisor = RuntimeProcessSupervisor(lease_store=store)

    active = {
        "lease_id": "active-1",
        "owner_kind": "run_attempt",
        "owner_id": "run-1:1",
        "pid": 22222,
        "status": "active",
    }
    closed = {
        "lease_id": "closed-1",
        "owner_kind": "ui_shell",
        "owner_id": "ui-1",
        "pid": 33333,
        "status": "closed",
    }
    store.upsert_active(active)
    store.upsert_active(closed)
    store.close("closed-1", reason="already_closed")

    monkeypatch.setattr(
        "server.services.platform.process_supervisor.terminate_pid_tree",
        lambda _pid: TerminationResult("terminated", "killed"),
    )
    reports = await supervisor.reap_orphan_leases_on_startup()

    assert len(reports) == 1
    assert reports[0]["lease_id"] == "active-1"
    assert reports[0]["outcome"] == "terminated"
    active_payload = store.get("active-1")
    assert isinstance(active_payload, dict)
    assert active_payload["status"] == "closed"
    closed_payload = store.get("closed-1")
    assert isinstance(closed_payload, dict)
    assert closed_payload["status"] == "closed"


@pytest.mark.asyncio
async def test_terminate_lease_async_falls_back_to_pid_when_process_ref_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = ProcessLeaseStore(tmp_path / "runs.db")
    supervisor = RuntimeProcessSupervisor(lease_store=store)
    store.upsert_active(
        {
            "lease_id": "lease-1",
            "owner_kind": "auth_session",
            "owner_id": "session-1",
            "pid": 44444,
            "status": "active",
        }
    )
    monkeypatch.setattr(
        "server.services.platform.process_supervisor.terminate_pid_tree",
        lambda _pid: TerminationResult("terminated", "pid_killed"),
    )
    result = await supervisor.terminate_lease_async("lease-1", reason="test")
    assert result.outcome == "terminated"
    payload = store.get("lease-1")
    assert isinstance(payload, dict)
    assert payload["status"] == "closed"


def test_terminate_lease_sync_with_missing_lease_returns_already_exited(tmp_path: Path) -> None:
    store = ProcessLeaseStore(tmp_path / "runs.db")
    supervisor = RuntimeProcessSupervisor(lease_store=store)
    result = supervisor.terminate_lease_sync("missing", reason="test")
    assert result.outcome == "already_exited"
    assert result.detail == "lease_not_found"
