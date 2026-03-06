from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from server.models import InteractiveErrorCode, RunStatus
from server.runtime.logging.structured_trace import log_event
from server.runtime.session.statechart import SessionEvent, waiting_recovery_event
from server.services.orchestration.workspace_manager import workspace_manager
from server.services.platform.process_supervisor import process_supervisor

logger = logging.getLogger(__name__)


def _parse_utc(raw: Any) -> datetime | None:
    if not isinstance(raw, str):
        return None
    normalized = raw.strip().replace("Z", "+00:00")
    if not normalized:
        return None
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class RunRecoveryService:
    async def _reconcile_missing_run_dir_before_resume_redrive(
        self,
        *,
        request_id: str,
        run_id: str,
        run_store_backend: Any,
    ) -> None:
        reason = "missing_run_dir_before_resume_redrive"
        await run_store_backend.update_run_status(run_id, RunStatus.FAILED)
        await run_store_backend.set_recovery_info(
            run_id,
            recovery_state="failed_reconciled",
            recovery_reason=reason,
        )
        await run_store_backend.clear_pending_interaction(request_id)
        await run_store_backend.clear_pending_auth_method_selection(request_id)
        await run_store_backend.clear_pending_auth(request_id)
        await run_store_backend.clear_engine_session_handle(request_id)
        await run_store_backend.clear_auth_resume_context(request_id)

    async def redrive_resume_ticket_if_needed(
        self,
        *,
        request_id: str,
        run_id: str,
        engine_name: str,
        run_store_backend: Any,
        resume_run_job: Callable[..., Any] | None,
        workspace_backend: Any | None = None,
        recovery_reason: str | None = None,
    ) -> bool:
        if not request_id or not run_id or resume_run_job is None:
            return False
        log_event(
            logger,
            event="recovery.redrive.requested",
            phase="recovery",
            outcome="start",
            request_id=request_id,
            run_id=run_id,
            engine=engine_name,
        )
        resume_ticket = await run_store_backend.get_resume_ticket(request_id)
        if not isinstance(resume_ticket, dict) or resume_ticket.get("state") not in {"issued", "dispatched"}:
            log_event(
                logger,
                event="recovery.redrive.skipped",
                phase="recovery",
                outcome="ok",
                request_id=request_id,
                run_id=run_id,
                engine=engine_name,
                error_code="NO_RESUME_TICKET",
            )
            return False
        request_record = await run_store_backend.get_request(request_id)
        if not isinstance(request_record, dict):
            log_event(
                logger,
                event="recovery.redrive.skipped",
                phase="recovery",
                outcome="ok",
                request_id=request_id,
                run_id=run_id,
                engine=engine_name,
                error_code="REQUEST_NOT_FOUND",
            )
            return False
        resolved_workspace = workspace_backend or workspace_manager
        run_dir = resolved_workspace.get_run_dir(run_id)
        if run_dir is None or not run_dir.exists():
            logger.warning(
                "Skip queued resume redrive because run_dir is missing: request_id=%s run_id=%s ticket_id=%s",
                request_id,
                run_id,
                resume_ticket.get("ticket_id"),
            )
            await self._reconcile_missing_run_dir_before_resume_redrive(
                request_id=request_id,
                run_id=run_id,
                run_store_backend=run_store_backend,
            )
            log_event(
                logger,
                event="recovery.reconciled_terminal",
                phase="recovery",
                outcome="ok",
                request_id=request_id,
                run_id=run_id,
                engine=engine_name,
                error_code="MISSING_RUN_DIR_BEFORE_REDRIVE",
            )
            return True
        effective_runtime_options = request_record.get(
            "effective_runtime_options",
            request_record.get("runtime_options", {}),
        )
        options = {
            **request_record.get("engine_options", {}),
            **(effective_runtime_options if isinstance(effective_runtime_options, dict) else {}),
            "__attempt_number_override": int(resume_ticket.get("target_attempt") or 1),
            "__resume_ticket_id": str(resume_ticket.get("ticket_id") or ""),
            "__resume_cause": str(resume_ticket.get("cause") or ""),
        }
        payload = resume_ticket.get("payload")
        if isinstance(payload, dict):
            if isinstance(payload.get("interaction_id"), int):
                options["__interactive_reply_interaction_id"] = payload.get("interaction_id")
            if "response" in payload:
                options["__interactive_reply_payload"] = payload.get("response")
            if isinstance(payload.get("resolution_mode"), str):
                options["__interactive_resolution_mode"] = payload.get("resolution_mode")
        task = resume_run_job(
            run_id=run_id,
            skill_id=str(request_record.get("skill_id") or ""),
            engine_name=engine_name,
            options=options,
            cache_key=None,
        )
        if asyncio.iscoroutine(task):
            asyncio.create_task(task)
        if recovery_reason:
            await run_store_backend.set_recovery_info(
                run_id,
                recovery_state="recovered_waiting",
                recovery_reason=recovery_reason,
            )
        log_event(
            logger,
            event="recovery.redrive.requested",
            phase="recovery",
            outcome="ok",
            request_id=request_id,
            run_id=run_id,
            attempt=int(resume_ticket.get("target_attempt") or 1),
            engine=engine_name,
            ticket_id=resume_ticket.get("ticket_id"),
        )
        return True

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
        resume_run_job: Callable[..., Any] | None = None,
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

        if run_status == RunStatus.WAITING_AUTH:
            pending_auth_method_selection = await run_store_backend.get_pending_auth_method_selection(request_id)
            pending_auth = await run_store_backend.get_pending_auth(request_id)
            expires_at = _parse_utc((pending_auth or {}).get("expires_at"))
            if expires_at is not None and expires_at <= datetime.now(timezone.utc):
                await mark_restart_reconciled_failed(
                    request_id=request_id,
                    run_id=run_id,
                    engine_name=engine_name,
                    error_code=InteractiveErrorCode.SESSION_RESUME_FAILED.value,
                    reason="pending auth session expired before restart recovery",
                )
                return
            if isinstance(pending_auth_method_selection, dict):
                await run_store_backend.update_run_status(run_id, RunStatus.WAITING_AUTH)
                await run_store_backend.set_recovery_info(
                    run_id,
                    recovery_state="recovered_waiting",
                    recovery_reason="resumable_auth_waiting_preserved",
                )
                return
            if isinstance(pending_auth, dict):
                await mark_restart_reconciled_failed(
                    request_id=request_id,
                    run_id=run_id,
                    engine_name=engine_name,
                    error_code=InteractiveErrorCode.SESSION_RESUME_FAILED.value,
                    reason="pending auth session cannot resume after restart",
                )
                return
            await mark_restart_reconciled_failed(
                request_id=request_id,
                run_id=run_id,
                engine_name=engine_name,
                error_code=InteractiveErrorCode.SESSION_RESUME_FAILED.value,
                reason="missing pending auth session after restart",
            )
            return

        if run_status == RunStatus.QUEUED:
            redriven = await self.redrive_resume_ticket_if_needed(
                request_id=request_id,
                run_id=run_id,
                engine_name=engine_name,
                run_store_backend=run_store_backend,
                resume_run_job=resume_run_job,
                recovery_reason="resume_ticket_redriven",
            )
            if redriven:
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
        await run_store_backend.clear_pending_auth_method_selection(request_id)
        await run_store_backend.clear_pending_auth(request_id)
        await run_store_backend.clear_engine_session_handle(request_id)
        await run_store_backend.clear_auth_resume_context(request_id)
        adapter = adapters.get(engine_name)
        if adapter is not None:
            with contextlib.suppress(Exception):
                await adapter.cancel_run_process(run_id)

    async def cleanup_orphan_runtime_bindings(self, records: list[dict[str, Any]]) -> None:
        reports = process_supervisor.consume_startup_orphan_reports()
        if not reports:
            return

        request_by_run: dict[str, str] = {}
        for record in records:
            record_run_id = str(record.get("run_id") or "").strip()
            record_request_id = str(record.get("request_id") or "").strip()
            if record_run_id and record_request_id:
                request_by_run[record_run_id] = record_request_id

        for report in reports:
            run_id: str | None = str(report.get("run_id") or "").strip() or None
            request_id: str | None = str(report.get("request_id") or "").strip() or None
            if request_id is None and run_id is not None:
                request_id = request_by_run.get(run_id)
            outcome_raw = str(report.get("outcome") or "unknown").strip().lower()
            outcome = "error" if outcome_raw == "failed" else "ok"
            log_event(
                logger,
                event="recovery.orphan_process.reaped",
                phase="recovery",
                outcome=outcome,
                level=logging.WARNING if outcome == "error" else logging.INFO,
                request_id=request_id,
                run_id=run_id,
                attempt=report.get("attempt_number") if isinstance(report.get("attempt_number"), int) else None,
                engine=str(report.get("engine") or "").strip() or None,
                owner_kind=str(report.get("owner_kind") or "").strip() or None,
                owner_id=str(report.get("owner_id") or "").strip() or None,
                pid=report.get("pid"),
                error_code="STARTUP_ORPHAN_REAP_FAILED" if outcome == "error" else "STARTUP_ORPHAN_REAP",
                error_type=str(report.get("detail") or "").strip() or None,
            )


run_recovery_service = RunRecoveryService()
