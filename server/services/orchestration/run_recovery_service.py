from __future__ import annotations

import contextlib
import logging
from typing import Any, Awaitable, Callable

from server.models import InteractiveErrorCode, RunStatus
from server.runtime.session.statechart import SessionEvent, waiting_recovery_event

logger = logging.getLogger(__name__)


class RunRecoveryService:
    async def recover_incomplete_runs_on_startup(
        self,
        *,
        run_store_backend: Any,
        concurrency_backend: Any,
        workspace_backend: Any,
        trust_manager_backend: Any,
        recover_single: Callable[[dict[str, Any]], Awaitable[None]],
        cleanup_orphan_bindings: Callable[[list[dict[str, Any]]], Awaitable[None]],
    ) -> None:
        records = await run_store_backend.list_incomplete_runs()
        if not records:
            concurrency_backend.reset_runtime_state()
            return

        for record in records:
            await recover_single(record)

        await cleanup_orphan_bindings(records)
        active_run_dirs: list[Any] = []
        for run_id in await run_store_backend.list_active_run_ids():
            run_dir = workspace_backend.get_run_dir(run_id)
            if run_dir:
                active_run_dirs.append(run_dir)
        try:
            trust_manager_backend.cleanup_stale_entries(active_run_dirs)
        except (OSError, RuntimeError, ValueError):
            logger.warning("Startup stale trust cleanup failed", exc_info=True)
        concurrency_backend.reset_runtime_state()

    async def recover_single_incomplete_run(
        self,
        *,
        record: dict[str, Any],
        run_store_backend: Any,
        is_valid_session_handle: Callable[[Any], bool],
        mark_restart_reconciled_failed: Callable[..., Awaitable[None]],
    ) -> None:
        request_id = str(record.get("request_id") or "")
        run_id = str(record.get("run_id") or "")
        run_status_raw = record.get("run_status")
        engine_name = str(record.get("engine") or "")
        if not request_id or not run_id or not isinstance(run_status_raw, str):
            return
        try:
            run_status = RunStatus(run_status_raw)
        except ValueError:
            return

        if run_status == RunStatus.WAITING_USER:
            pending = await run_store_backend.get_pending_interaction(request_id)
            handle = await run_store_backend.get_engine_session_handle(request_id)
            recovery_event = waiting_recovery_event(
                has_pending_interaction=isinstance(pending, dict),
                has_valid_handle=is_valid_session_handle(handle),
            )
            if recovery_event == SessionEvent.RESTART_PRESERVE_WAITING:
                await run_store_backend.update_run_status(run_id, RunStatus.WAITING_USER)
                await run_store_backend.set_recovery_info(
                    run_id,
                    recovery_state="recovered_waiting",
                    recovery_reason="resumable_waiting_preserved",
                )
                return
            await mark_restart_reconciled_failed(
                request_id=request_id,
                run_id=run_id,
                engine_name=engine_name,
                error_code=InteractiveErrorCode.SESSION_RESUME_FAILED.value,
                reason="missing pending interaction or session handle after restart",
            )
            return

        if run_status in {RunStatus.QUEUED, RunStatus.RUNNING}:
            await mark_restart_reconciled_failed(
                request_id=request_id,
                run_id=run_id,
                engine_name=engine_name,
                error_code=InteractiveErrorCode.ORCHESTRATOR_RESTART_INTERRUPTED.value,
                reason=f"{run_status.value} run interrupted by orchestrator restart",
            )

    async def mark_restart_reconciled_failed(
        self,
        *,
        request_id: str,
        run_id: str,
        engine_name: str,
        error_code: str,
        reason: str,
        run_store_backend: Any,
        workspace_backend: Any,
        update_status: Callable[..., None],
        adapters: dict[str, Any],
    ) -> None:
        message = f"{error_code}: {reason}"
        run_dir = workspace_backend.get_run_dir(run_id)
        if run_dir:
            update_status(
                run_dir,
                RunStatus.FAILED,
                error={"code": error_code, "message": message},
                effective_session_timeout_sec=await run_store_backend.get_effective_session_timeout(request_id),
            )
        await run_store_backend.update_run_status(run_id, RunStatus.FAILED)
        await run_store_backend.set_recovery_info(
            run_id,
            recovery_state="failed_reconciled",
            recovery_reason=reason,
        )
        await run_store_backend.clear_pending_interaction(request_id)
        await run_store_backend.clear_engine_session_handle(request_id)
        adapter = adapters.get(engine_name)
        if adapter is not None:
            with contextlib.suppress(Exception):
                await adapter.cancel_run_process(run_id)

    async def cleanup_orphan_runtime_bindings(self, records: list[dict[str, Any]]) -> None:
        _ = records
