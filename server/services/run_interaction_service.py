from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, HTTPException  # type: ignore[import-not-found]

from ..models import (
    ExecutionMode,
    InteractiveErrorCode,
    InteractionPendingResponse,
    InteractionReplyRequest,
    InteractionReplyResponse,
    PendingInteraction,
    RunStatus,
)
from .concurrency_manager import concurrency_manager
from .job_orchestrator import job_orchestrator
from .run_source_adapter import RunSourceAdapter, get_request_and_run_dir, require_capability
from .run_store import run_store


class RunInteractionService:
    async def get_pending(
        self,
        *,
        source_adapter: RunSourceAdapter,
        request_id: str,
        run_store_backend: Any = run_store,
    ) -> InteractionPendingResponse:
        require_capability(source_adapter, capability="supports_pending_reply")
        request_record, run_dir = get_request_and_run_dir(source_adapter, request_id)
        _ensure_interactive_mode(request_record)
        status, _, _, _ = _read_run_status(run_dir)
        pending_payload = run_store_backend.get_pending_interaction(request_id)
        pending = None
        if pending_payload and status == RunStatus.WAITING_USER:
            pending = PendingInteraction.model_validate(pending_payload)
        return InteractionPendingResponse(
            request_id=request_id,
            status=status,
            pending=pending,
        )

    async def submit_reply(
        self,
        *,
        source_adapter: RunSourceAdapter,
        request_id: str,
        request: InteractionReplyRequest,
        background_tasks: BackgroundTasks,
        run_store_backend: Any = run_store,
    ) -> InteractionReplyResponse:
        require_capability(source_adapter, capability="supports_pending_reply")
        request_record, run_dir = get_request_and_run_dir(source_adapter, request_id)
        _ensure_interactive_mode(request_record)
        status, warnings, _, _ = _read_run_status(run_dir)
        if status != RunStatus.WAITING_USER:
            replay = _resolve_idempotent_replay(
                request_id=request_id,
                request=request,
                status=status,
                run_store_backend=run_store_backend,
            )
            if replay:
                return replay
            raise HTTPException(status_code=409, detail="Run is not waiting for user interaction")

        pending_payload = run_store_backend.get_pending_interaction(request_id)
        if not pending_payload:
            replay = _resolve_idempotent_replay(
                request_id=request_id,
                request=request,
                status=status,
                run_store_backend=run_store_backend,
            )
            if replay:
                return replay
            raise HTTPException(status_code=409, detail="No pending interaction")

        raw_interaction_id = pending_payload.get("interaction_id")
        if isinstance(raw_interaction_id, int):
            current_interaction_id = raw_interaction_id
        elif isinstance(raw_interaction_id, str):
            try:
                current_interaction_id = int(raw_interaction_id)
            except ValueError:
                raise HTTPException(status_code=409, detail="stale interaction")
        else:
            raise HTTPException(status_code=409, detail="stale interaction")
        if request.interaction_id != current_interaction_id:
            raise HTTPException(status_code=409, detail="stale interaction")

        reply_state = run_store_backend.submit_interaction_reply(
            request_id=request_id,
            interaction_id=request.interaction_id,
            response=request.response,
            idempotency_key=request.idempotency_key,
        )
        if reply_state == "idempotent":
            return InteractionReplyResponse(request_id=request_id, status=status, accepted=True)
        if reply_state == "idempotency_conflict":
            raise HTTPException(
                status_code=409,
                detail="idempotency_key already used with different response",
            )
        if reply_state == "stale":
            raise HTTPException(status_code=409, detail="stale interaction")

        profile = run_store_backend.get_interactive_profile(request_id) or {}
        if profile.get("kind") == "sticky_process":
            sticky_runtime = run_store_backend.get_sticky_wait_runtime(request_id)
            if not sticky_runtime:
                await _mark_run_failed(
                    source_adapter=source_adapter,
                    request_id=request_id,
                    request_record=request_record,
                    run_dir=run_dir,
                    code=InteractiveErrorCode.INTERACTION_PROCESS_LOST.value,
                    message="Sticky process runtime missing",
                    run_store_backend=run_store_backend,
                )
                raise HTTPException(status_code=409, detail="sticky process lost")
            deadline_raw = sticky_runtime.get("wait_deadline_at")
            process_binding = sticky_runtime.get("process_binding") or {}
            if not deadline_raw:
                await _mark_run_failed(
                    source_adapter=source_adapter,
                    request_id=request_id,
                    request_record=request_record,
                    run_dir=run_dir,
                    code=InteractiveErrorCode.INTERACTION_PROCESS_LOST.value,
                    message="Sticky process deadline missing",
                    run_store_backend=run_store_backend,
                )
                raise HTTPException(status_code=409, detail="sticky process lost")
            try:
                deadline = datetime.fromisoformat(str(deadline_raw))
            except ValueError:
                await _mark_run_failed(
                    source_adapter=source_adapter,
                    request_id=request_id,
                    request_record=request_record,
                    run_dir=run_dir,
                    code=InteractiveErrorCode.INTERACTION_PROCESS_LOST.value,
                    message="Sticky process deadline invalid",
                    run_store_backend=run_store_backend,
                )
                raise HTTPException(status_code=409, detail="sticky process lost")
            if datetime.utcnow() > deadline:
                await _mark_run_failed(
                    source_adapter=source_adapter,
                    request_id=request_id,
                    request_record=request_record,
                    run_dir=run_dir,
                    code=InteractiveErrorCode.INTERACTION_WAIT_TIMEOUT.value,
                    message="Sticky process wait timeout",
                    run_store_backend=run_store_backend,
                )
                raise HTTPException(status_code=409, detail="interaction wait timeout")
            if process_binding.get("alive") is False:
                await _mark_run_failed(
                    source_adapter=source_adapter,
                    request_id=request_id,
                    request_record=request_record,
                    run_dir=run_dir,
                    code=InteractiveErrorCode.INTERACTION_PROCESS_LOST.value,
                    message="Sticky process exited",
                    run_store_backend=run_store_backend,
                )
                raise HTTPException(status_code=409, detail="sticky process lost")

        is_sticky_profile = profile.get("kind") == "sticky_process"
        next_status = RunStatus.RUNNING if is_sticky_profile else RunStatus.QUEUED
        _write_run_status(run_dir, next_status, warnings=warnings)

        run_id_obj = request_record.get("run_id")
        run_id = run_id_obj if isinstance(run_id_obj, str) else None
        if run_id:
            run_store_backend.update_run_status(run_id, next_status)
            merged_options = {
                **request_record.get("engine_options", {}),
                **request_record.get("runtime_options", {}),
                "__interactive_reply_payload": request.response,
                "__interactive_reply_interaction_id": request.interaction_id,
                "__interactive_resolution_mode": "user_reply",
            }
            if is_sticky_profile:
                merged_options["__sticky_slot_held"] = True
                job_orchestrator.cancel_sticky_watchdog(request_id)
            else:
                admitted = await concurrency_manager.admit_or_reject()
                if not admitted:
                    raise HTTPException(status_code=429, detail="Job queue is full")

            temp_request_id = source_adapter.get_run_job_temp_request_id(request_id)
            background_tasks.add_task(
                job_orchestrator.run_job,
                run_id=run_id,
                skill_id=str(request_record["skill_id"]),
                engine_name=str(request_record["engine"]),
                options=merged_options,
                cache_key=None,
                temp_request_id=temp_request_id,
            )

        return InteractionReplyResponse(
            request_id=request_id,
            status=next_status,
            accepted=True,
        )


def _ensure_interactive_mode(request_record: dict[str, Any]) -> None:
    runtime_options = request_record.get("runtime_options", {})
    execution_mode = runtime_options.get("execution_mode", ExecutionMode.AUTO.value)
    if execution_mode != ExecutionMode.INTERACTIVE.value:
        raise HTTPException(
            status_code=400,
            detail="Interaction endpoints require runtime_options.execution_mode=interactive",
        )


def _read_run_status(run_dir: Path) -> tuple[RunStatus, list[Any], Any, str]:
    status_file = run_dir / "status.json"
    current_status = RunStatus.QUEUED
    warnings: list[Any] = []
    error: Any = None
    updated_at = ""
    if status_file.exists():
        payload = json.loads(status_file.read_text(encoding="utf-8"))
        current_status = RunStatus(payload.get("status", RunStatus.QUEUED.value))
        warnings = payload.get("warnings", [])
        error = payload.get("error")
        updated_at = payload.get("updated_at", "")
    return current_status, warnings, error, updated_at


def _write_run_status(
    run_dir: Path,
    status: RunStatus,
    warnings: list[Any] | None = None,
    error: Any = None,
    effective_session_timeout_sec: int | None = None,
) -> None:
    status_file = run_dir / "status.json"
    existing_timeout = None
    if status_file.exists():
        try:
            existing = json.loads(status_file.read_text(encoding="utf-8"))
            existing_timeout = existing.get("effective_session_timeout_sec")
        except Exception:
            existing_timeout = None
    payload = {
        "status": status.value if isinstance(status, RunStatus) else str(status),
        "updated_at": datetime.now().isoformat(),
        "warnings": warnings or [],
        "error": error,
        "effective_session_timeout_sec": (
            effective_session_timeout_sec
            if effective_session_timeout_sec is not None
            else existing_timeout
        ),
    }
    status_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def _mark_run_failed(
    *,
    source_adapter: RunSourceAdapter,
    request_id: str,
    request_record: dict[str, Any],
    run_dir: Path,
    code: str,
    message: str,
    run_store_backend: Any,
) -> None:
    error_payload = {"code": code, "message": message}
    _write_run_status(
        run_dir,
        RunStatus.FAILED,
        error=error_payload,
        effective_session_timeout_sec=run_store_backend.get_effective_session_timeout(request_id),
    )
    run_id = request_record.get("run_id")
    if run_id:
        run_store_backend.update_run_status(run_id, RunStatus.FAILED)
        await concurrency_manager.release_slot()
    source_adapter.mark_failed(request_id, message)


def _resolve_idempotent_replay(
    request_id: str,
    request: InteractionReplyRequest,
    status: RunStatus,
    run_store_backend: Any,
) -> InteractionReplyResponse | None:
    if not request.idempotency_key:
        return None
    existing_reply = run_store_backend.get_interaction_reply(
        request_id=request_id,
        interaction_id=request.interaction_id,
        idempotency_key=request.idempotency_key,
    )
    if existing_reply is None:
        return None
    if existing_reply != request.response:
        raise HTTPException(
            status_code=409,
            detail="idempotency_key already used with different response",
        )
    return InteractionReplyResponse(
        request_id=request_id,
        status=status,
        accepted=True,
    )


run_interaction_service = RunInteractionService()
