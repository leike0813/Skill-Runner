from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from fastapi import BackgroundTasks, HTTPException  # type: ignore[import-not-found]

from server.models import (
    AuthSessionStatusResponse,
    ClientConversationMode,
    ExecutionMode,
    InteractionPendingResponse,
    InteractionReplyRequest,
    InteractionReplyResponse,
    OrchestratorEventType,
    PendingAuth,
    PendingAuthMethodSelection,
    PendingInteraction,
    PendingOwner,
    ResumeCause,
    RunStatus,
)
from server.runtime.observability.run_source_adapter import (
    RunSourceAdapter,
    get_request_and_run_dir,
    require_capability,
)
from server.runtime.protocol.factories import make_resume_command
from server.runtime.protocol.schema_registry import ProtocolSchemaViolation, validate_resume_command
from server.runtime.session.statechart import waiting_reply_target_status
from server.services.orchestration.job_orchestrator import job_orchestrator
from server.services.orchestration.run_auth_orchestration_service import (
    run_auth_orchestration_service,
)
from server.services.orchestration.run_execution_core import resolve_conversation_mode
from server.services.orchestration.run_projection_service import run_projection_service
from server.services.orchestration.run_store import run_store
from server.services.platform.async_compat import maybe_await


class RunInteractionService:
    async def get_pending(
        self,
        *,
        source_adapter: RunSourceAdapter,
        request_id: str,
        run_store_backend: Any = run_store,
    ) -> InteractionPendingResponse:
        require_capability(source_adapter, capability="supports_pending_reply")
        request_record, run_dir = await get_request_and_run_dir(source_adapter, request_id)
        status, _, _, _ = _read_run_status(run_dir)
        pending_payload = await maybe_await(run_store_backend.get_pending_interaction(request_id))
        pending_auth_method_selection_payload = await maybe_await(
            run_store_backend.get_pending_auth_method_selection(request_id)
        )
        pending_auth_payload = await maybe_await(run_store_backend.get_pending_auth(request_id))
        pending = None
        pending_auth_method_selection = None
        pending_auth = None
        if pending_payload and status == RunStatus.WAITING_USER:
            pending = PendingInteraction.model_validate(pending_payload)
        pending_owner = None
        if pending_auth_payload and status == RunStatus.WAITING_AUTH:
            pending_auth = PendingAuth.model_validate(pending_auth_payload)
            pending_owner = PendingOwner.WAITING_AUTH_CHALLENGE
        elif pending_auth_method_selection_payload and status == RunStatus.WAITING_AUTH:
            pending_auth_method_selection = PendingAuthMethodSelection.model_validate(
                pending_auth_method_selection_payload
            )
            pending_owner = PendingOwner.WAITING_AUTH_METHOD_SELECTION
        if pending is not None and status == RunStatus.WAITING_USER:
            pending_owner = PendingOwner.WAITING_USER
        policy_fields = _build_runtime_policy_fields(request_record)
        return InteractionPendingResponse(
            request_id=request_id,
            status=status,
            requested_execution_mode=policy_fields["requested_execution_mode"],
            effective_execution_mode=policy_fields["effective_execution_mode"],
            conversation_mode=policy_fields["conversation_mode"],
            effective_interactive_require_user_reply=policy_fields["effective_interactive_require_user_reply"],
            effective_interactive_reply_timeout_sec=policy_fields["effective_interactive_reply_timeout_sec"],
            pending=pending,
            pending_auth_method_selection=pending_auth_method_selection,
            pending_auth=pending_auth,
            pending_owner=pending_owner,
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
        request_record, run_dir = await get_request_and_run_dir(source_adapter, request_id)
        status, warnings, _, _ = _read_run_status(run_dir)
        run_id_obj = request_record.get("run_id")
        run_id = run_id_obj if isinstance(run_id_obj, str) else None
        if request.mode == "auth":
            if status != RunStatus.WAITING_AUTH:
                raise HTTPException(status_code=409, detail="Run is not waiting for auth")
            if not run_id:
                raise HTTPException(status_code=404, detail="Run not found")
            if request.selection is not None:
                return await run_auth_orchestration_service.select_auth_method(
                    request_id=request_id,
                    run_id=run_id,
                    selection=request.selection,
                    background_tasks=background_tasks,
                    run_store_backend=run_store_backend,
                    append_orchestrator_event=job_orchestrator._append_orchestrator_event,
                    update_status=job_orchestrator._update_status,
                    resume_run_job=job_orchestrator.run_job,
                )
            if request.submission is None or request.auth_session_id is None:
                raise HTTPException(status_code=422, detail="Auth submission is incomplete")
            return await run_auth_orchestration_service.submit_auth_input(
                request_id=request_id,
                run_id=run_id,
                request=request.submission,
                auth_session_id=request.auth_session_id,
                background_tasks=background_tasks,
                run_store_backend=run_store_backend,
                append_orchestrator_event=job_orchestrator._append_orchestrator_event,
                update_status=job_orchestrator._update_status,
                resume_run_job=job_orchestrator.run_job,
            )
        _ensure_interactive_mode(request_record)
        if status != RunStatus.WAITING_USER:
            replay = await _resolve_idempotent_replay(
                request_id=request_id,
                request=request,
                status=status,
                run_store_backend=run_store_backend,
            )
            if replay:
                return replay
            raise HTTPException(status_code=409, detail="Run is not waiting for user interaction")

        pending_payload = await maybe_await(run_store_backend.get_pending_interaction(request_id))
        if not pending_payload:
            replay = await _resolve_idempotent_replay(
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

        reply_state = await maybe_await(run_store_backend.submit_interaction_reply(
            request_id=request_id,
            interaction_id=request.interaction_id,
            response=request.response,
            idempotency_key=request.idempotency_key,
        ))
        if reply_state == "idempotent":
            return InteractionReplyResponse(request_id=request_id, status=status, accepted=True)
        if reply_state == "idempotency_conflict":
            raise HTTPException(
                status_code=409,
                detail="idempotency_key already used with different response",
            )
        if reply_state == "stale":
            raise HTTPException(status_code=409, detail="stale interaction")
        source_attempt = int(pending_payload.get("source_attempt") or 1)

        next_status = waiting_reply_target_status()

        if run_id:
            await run_projection_service.write_non_terminal_projection(
                run_dir=run_dir,
                request_id=request_id,
                run_id=run_id,
                status=next_status,
                request_record=request_record,
                current_attempt=source_attempt,
                pending_owner=None,
                source_attempt=source_attempt,
                target_attempt=source_attempt + 1,
                warnings=warnings,
                effective_session_timeout_sec=await maybe_await(
                    run_store_backend.get_effective_session_timeout(request_id)
                ),
                run_store_backend=run_store_backend,
            )
            await maybe_await(run_store_backend.update_run_status(run_id, next_status))
            resume_command = make_resume_command(
                interaction_id=request.interaction_id,
                response=request.response,
                resolution_mode="user_reply",
            )
            try:
                validate_resume_command(resume_command)
            except ProtocolSchemaViolation as exc:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "PROTOCOL_SCHEMA_VIOLATION",
                        "message": str(exc),
                    },
                ) from exc
            merged_options = {
                **request_record.get("engine_options", {}),
                **request_record.get(
                    "effective_runtime_options",
                    request_record.get("runtime_options", {}),
                ),
                "__interactive_reply_payload": resume_command["response"],
                "__interactive_reply_interaction_id": resume_command["interaction_id"],
                "__interactive_resolution_mode": resume_command["resolution_mode"],
                "__interactive_source_attempt": source_attempt,
                "__attempt_number_override": source_attempt + 1,
            }
            resume_ticket = await maybe_await(
                run_store_backend.issue_resume_ticket(
                    request_id,
                    cause=ResumeCause.INTERACTION_REPLY.value,
                    source_attempt=source_attempt,
                    target_attempt=source_attempt + 1,
                    payload={
                        "interaction_id": request.interaction_id,
                        "resolution_mode": resume_command["resolution_mode"],
                        "response": resume_command["response"],
                    },
                )
            )
            merged_options["__resume_ticket_id"] = str(resume_ticket["ticket_id"])
            merged_options["__resume_cause"] = ResumeCause.INTERACTION_REPLY.value
            await run_projection_service.write_non_terminal_projection(
                run_dir=run_dir,
                request_id=request_id,
                run_id=run_id,
                status=next_status,
                request_record=request_record,
                current_attempt=source_attempt,
                pending_owner=None,
                resume_ticket_id=str(resume_ticket["ticket_id"]),
                resume_cause=ResumeCause.INTERACTION_REPLY,
                source_attempt=source_attempt,
                target_attempt=source_attempt + 1,
                warnings=warnings,
                effective_session_timeout_sec=await maybe_await(
                    run_store_backend.get_effective_session_timeout(request_id)
                ),
                run_store_backend=run_store_backend,
            )
            accepted_at = datetime.now().astimezone().isoformat()
            job_orchestrator._append_orchestrator_event(
                run_dir=run_dir,
                attempt_number=source_attempt + 1,
                category="interaction",
                type_name=OrchestratorEventType.INTERACTION_REPLY_ACCEPTED.value,
                data={
                    "interaction_id": request.interaction_id,
                    "resolution_mode": "user_reply",
                    "accepted_at": accepted_at,
                    "response_preview": _extract_response_preview(request.response),
                },
            )
            ticket_dispatched = await maybe_await(
                run_store_backend.mark_resume_ticket_dispatched(
                    request_id,
                    str(resume_ticket["ticket_id"]),
                )
            )
            temp_request_id = source_adapter.get_run_job_temp_request_id(request_id)
            if ticket_dispatched:
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

    async def get_auth_session_status(
        self,
        *,
        source_adapter: RunSourceAdapter,
        request_id: str,
        run_store_backend: Any = run_store,
    ) -> AuthSessionStatusResponse:
        require_capability(source_adapter, capability="supports_pending_reply")
        request_record, _ = await get_request_and_run_dir(source_adapter, request_id)
        response = await run_auth_orchestration_service.get_auth_session_status(
            request_id=request_id,
            append_orchestrator_event=job_orchestrator._append_orchestrator_event,
            update_status=job_orchestrator._update_status,
            resume_run_job=job_orchestrator.run_job,
            run_store_backend=run_store_backend,
        )
        policy_fields = _build_runtime_policy_fields(request_record)
        response.requested_execution_mode = policy_fields["requested_execution_mode"]
        response.effective_execution_mode = policy_fields["effective_execution_mode"]
        response.conversation_mode = policy_fields["conversation_mode"]
        response.effective_interactive_require_user_reply = policy_fields[
            "effective_interactive_require_user_reply"
        ]
        response.effective_interactive_reply_timeout_sec = policy_fields[
            "effective_interactive_reply_timeout_sec"
        ]
        return response


def _ensure_interactive_mode(request_record: dict[str, Any]) -> None:
    runtime_options = request_record.get(
        "effective_runtime_options",
        request_record.get("runtime_options", {}),
    )
    execution_mode = runtime_options.get("execution_mode", ExecutionMode.AUTO.value)
    if execution_mode != ExecutionMode.INTERACTIVE.value:
        raise HTTPException(
            status_code=400,
            detail="Interaction endpoints require effective execution_mode=interactive",
        )


def _read_run_status(run_dir: Path) -> tuple[RunStatus, list[Any], Any, str]:
    status_file = run_dir / ".state" / "state.json"
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
    status_file = run_dir / ".state" / "state.json"
    existing_timeout = None
    if status_file.exists():
        try:
            existing = json.loads(status_file.read_text(encoding="utf-8"))
            existing_runtime = existing.get("runtime") if isinstance(existing.get("runtime"), dict) else {}
            existing_timeout = existing_runtime.get("effective_session_timeout_sec")
        except (OSError, ValueError, TypeError):
            existing_timeout = None
    payload: dict[str, Any] = existing if status_file.exists() and isinstance(existing, dict) else {}
    payload["status"] = status.value if isinstance(status, RunStatus) else str(status)
    payload["updated_at"] = datetime.now().isoformat()
    payload["warnings"] = warnings or []
    payload["error"] = error
    runtime_obj = payload.get("runtime")
    runtime_payload: dict[str, Any] = cast(dict[str, Any], runtime_obj) if isinstance(runtime_obj, dict) else {}
    runtime_payload["effective_session_timeout_sec"] = (
        effective_session_timeout_sec
        if effective_session_timeout_sec is not None
        else existing_timeout
    )
    payload["runtime"] = runtime_payload
    status_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def _resolve_idempotent_replay(
    request_id: str,
    request: InteractionReplyRequest,
    status: RunStatus,
    run_store_backend: Any,
) -> InteractionReplyResponse | None:
    if not request.idempotency_key:
        return None
    existing_reply = await maybe_await(run_store_backend.get_interaction_reply(
        request_id=request_id,
        interaction_id=request.interaction_id,
        idempotency_key=request.idempotency_key,
    ))
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


def _build_runtime_policy_fields(request_record: dict[str, Any]) -> dict[str, Any]:
    runtime_options = request_record.get("runtime_options", {})
    effective_runtime_options = request_record.get(
        "effective_runtime_options",
        runtime_options,
    )
    requested_execution_mode = _coerce_execution_mode(
        runtime_options.get("execution_mode", ExecutionMode.AUTO.value)
        if isinstance(runtime_options, dict)
        else ExecutionMode.AUTO.value
    )
    effective_execution_mode = _coerce_execution_mode(
        effective_runtime_options.get("execution_mode", ExecutionMode.AUTO.value)
        if isinstance(effective_runtime_options, dict)
        else ExecutionMode.AUTO.value
    )
    conversation_mode = _coerce_conversation_mode(
        resolve_conversation_mode(request_record.get("client_metadata"))
    )
    interactive_reply_timeout_sec = None
    if isinstance(effective_runtime_options, dict):
        timeout_obj = effective_runtime_options.get("interactive_reply_timeout_sec")
        if isinstance(timeout_obj, int):
            interactive_reply_timeout_sec = timeout_obj
    return {
        "requested_execution_mode": requested_execution_mode,
        "effective_execution_mode": effective_execution_mode,
        "conversation_mode": conversation_mode,
        "effective_interactive_require_user_reply": bool(
            effective_execution_mode == ExecutionMode.INTERACTIVE
            and conversation_mode == ClientConversationMode.SESSION
        ),
        "effective_interactive_reply_timeout_sec": interactive_reply_timeout_sec,
    }


def _coerce_execution_mode(raw: Any) -> ExecutionMode | None:
    if isinstance(raw, ExecutionMode):
        return raw
    if isinstance(raw, str):
        try:
            return ExecutionMode(raw)
        except ValueError:
            return None
    return None


def _coerce_conversation_mode(raw: Any) -> ClientConversationMode | None:
    if isinstance(raw, ClientConversationMode):
        return raw
    if isinstance(raw, str):
        try:
            return ClientConversationMode(raw)
        except ValueError:
            return None
    return None


run_interaction_service = RunInteractionService()


def _extract_response_preview(response: Any) -> str | None:
    if isinstance(response, dict):
        text_obj = response.get("text")
        if isinstance(text_obj, str):
            normalized = text_obj.strip()
            return normalized or None
    if isinstance(response, str):
        normalized = response.strip()
        return normalized or None
    return None
