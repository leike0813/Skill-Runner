from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import logging

import pytest

from server.models import InteractiveErrorCode, RunStatus
from server.services.orchestration.run_recovery_service import RunRecoveryService


@pytest.mark.asyncio
async def test_recover_waiting_auth_fails_when_pending_auth_cannot_resume_after_restart():
    backend = SimpleNamespace(
        get_pending_auth_method_selection=AsyncMock(return_value=None),
        get_pending_auth=AsyncMock(
            return_value={
                "auth_session_id": "auth-1",
                "phase": "challenge_active",
                "created_at": "2026-03-03T00:00:00Z",
                "expires_at": "2099-03-03T00:15:00Z",
            }
        ),
    )
    mark_restart_reconciled_failed = AsyncMock()

    service = RunRecoveryService()
    await service.recover_single_incomplete_run(
        record={
            "request_id": "req-1",
            "run_id": "run-1",
            "run_status": RunStatus.WAITING_AUTH.value,
            "engine": "codex",
        },
        run_store_backend=backend,
        is_valid_session_handle=lambda _handle: False,
        mark_restart_reconciled_failed=mark_restart_reconciled_failed,
    )

    mark_restart_reconciled_failed.assert_awaited_once_with(
        request_id="req-1",
        run_id="run-1",
        engine_name="codex",
        error_code=InteractiveErrorCode.SESSION_RESUME_FAILED.value,
        reason="pending auth session cannot resume after restart",
    )


@pytest.mark.asyncio
async def test_recover_waiting_auth_preserves_method_selection():
    backend = SimpleNamespace(
        get_pending_auth_method_selection=AsyncMock(return_value={"available_methods": ["callback"]}),
        get_pending_auth=AsyncMock(return_value=None),
        update_run_status=AsyncMock(),
        set_recovery_info=AsyncMock(),
    )
    mark_restart_reconciled_failed = AsyncMock()

    service = RunRecoveryService()
    await service.recover_single_incomplete_run(
        record={
            "request_id": "req-1",
            "run_id": "run-1",
            "run_status": RunStatus.WAITING_AUTH.value,
            "engine": "codex",
        },
        run_store_backend=backend,
        is_valid_session_handle=lambda _handle: False,
        mark_restart_reconciled_failed=mark_restart_reconciled_failed,
    )

    backend.update_run_status.assert_awaited_once_with("run-1", RunStatus.WAITING_AUTH)
    backend.set_recovery_info.assert_awaited_once_with(
        "run-1",
        recovery_state="recovered_waiting",
        recovery_reason="resumable_auth_waiting_preserved",
    )
    mark_restart_reconciled_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_redrive_resume_ticket_existing_run_dir_schedules_resume_once(tmp_path: Path):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir(parents=True, exist_ok=True)
    backend = SimpleNamespace(
        get_resume_ticket=AsyncMock(
            return_value={
                "ticket_id": "ticket-1",
                "state": "dispatched",
                "target_attempt": 2,
                "cause": "interaction_reply",
                "payload": {"interaction_id": 1, "response": {"text": "hi"}, "resolution_mode": "user_reply"},
            }
        ),
        get_request=AsyncMock(
            return_value={
                "skill_id": "skill-1",
                "engine_options": {},
                "runtime_options": {"execution_mode": "interactive"},
                "effective_runtime_options": {"execution_mode": "interactive"},
            }
        ),
        set_recovery_info=AsyncMock(),
    )
    resume_run_job = Mock(return_value=None)

    service = RunRecoveryService()
    handled = await service.redrive_resume_ticket_if_needed(
        request_id="req-1",
        run_id="run-1",
        engine_name="codex",
        run_store_backend=backend,
        resume_run_job=resume_run_job,
        workspace_backend=SimpleNamespace(get_run_dir=lambda _run_id: run_dir),
        recovery_reason="resume_ticket_redriven_online",
    )

    assert handled is True
    resume_run_job.assert_called_once()
    backend.set_recovery_info.assert_awaited_once_with(
        "run-1",
        recovery_state="recovered_waiting",
        recovery_reason="resume_ticket_redriven_online",
    )


@pytest.mark.asyncio
async def test_redrive_resume_ticket_missing_run_dir_reconciles_failed():
    backend = SimpleNamespace(
        get_resume_ticket=AsyncMock(
            return_value={
                "ticket_id": "ticket-1",
                "state": "dispatched",
                "target_attempt": 2,
                "cause": "interaction_reply",
                "payload": {"interaction_id": 1, "response": {"text": "hi"}, "resolution_mode": "user_reply"},
            }
        ),
        get_request=AsyncMock(
            return_value={
                "skill_id": "skill-1",
                "engine_options": {},
                "runtime_options": {"execution_mode": "interactive"},
                "effective_runtime_options": {"execution_mode": "interactive"},
            }
        ),
        update_run_status=AsyncMock(),
        set_recovery_info=AsyncMock(),
        clear_pending_interaction=AsyncMock(),
        clear_pending_auth_method_selection=AsyncMock(),
        clear_pending_auth=AsyncMock(),
        list_active_durable_auth_sessions_for_request=AsyncMock(return_value=[]),
        mark_durable_auth_session_terminal=AsyncMock(),
        clear_engine_session_handle=AsyncMock(),
        clear_auth_resume_context=AsyncMock(),
    )
    resume_run_job = Mock(return_value=None)

    service = RunRecoveryService()
    handled = await service.redrive_resume_ticket_if_needed(
        request_id="req-1",
        run_id="run-1",
        engine_name="codex",
        run_store_backend=backend,
        resume_run_job=resume_run_job,
        workspace_backend=SimpleNamespace(get_run_dir=lambda _run_id: None),
        recovery_reason="resume_ticket_redriven_online",
    )

    assert handled is True
    resume_run_job.assert_not_called()
    backend.update_run_status.assert_awaited_once_with("run-1", RunStatus.FAILED)
    backend.set_recovery_info.assert_awaited_once_with(
        "run-1",
        recovery_state="failed_reconciled",
        recovery_reason="missing_run_dir_before_resume_redrive",
    )
    backend.clear_pending_interaction.assert_awaited_once_with("req-1")
    backend.clear_pending_auth_method_selection.assert_awaited_once_with("req-1")
    backend.clear_pending_auth.assert_awaited_once_with("req-1")
    backend.clear_engine_session_handle.assert_awaited_once_with("req-1")
    backend.clear_auth_resume_context.assert_awaited_once_with("req-1")


@pytest.mark.asyncio
async def test_cleanup_orphan_runtime_bindings_logs_startup_reap(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(
        "server.services.orchestration.run_recovery_service.process_supervisor.consume_startup_orphan_reports",
        lambda: [
            {
                "lease_id": "lease-1",
                "owner_kind": "run_attempt",
                "owner_id": "run-1:1",
                "request_id": None,
                "run_id": "run-1",
                "attempt_number": 1,
                "engine": "codex",
                "pid": 12345,
                "outcome": "terminated",
                "detail": "killed",
            }
        ],
    )
    service = RunRecoveryService()
    await service.cleanup_orphan_runtime_bindings(
        records=[{"request_id": "req-1", "run_id": "run-1"}]
    )
    assert "event=\"recovery.orphan_process.reaped\"" in caplog.text
    assert "request_id=\"req-1\"" in caplog.text
