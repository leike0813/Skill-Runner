import json
import logging
import contextlib
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, Request, UploadFile  # type: ignore[import-not-found]

from ..models import (
    AuthSessionStatusResponse,
    CancelResponse,
    ClientConversationMode,
    DispatchPhase,
    ExecutionMode,
    InteractionPendingResponse,
    InteractionReplyRequest,
    InteractionReplyResponse,
    PendingOwner,
    RecoveryState,
    RequestStatusResponse,
    ResumeCause,
    RunLocalSkillSource,
    RunArtifactsResponse,
    RunCreateRequest,
    RunLogsResponse,
    RunResultResponse,
    RunStatus,
    TempSkillRunCreateRequest,
    TempSkillRunCreateResponse,
    TempSkillRunUploadResponse,
)
from ..services.platform.concurrency_manager import concurrency_manager
from ..services.platform.async_compat import maybe_await
from ..services.orchestration.job_orchestrator import job_orchestrator
from ..services.engine_management.model_registry import model_registry
from ..services.orchestration.runtime_observability_ports import install_runtime_observability_ports
from ..services.orchestration.runtime_protocol_ports import install_runtime_protocol_ports
from ..services.platform.cache_key_builder import (
    compute_bytes_hash,
    compute_cache_key,
    compute_inline_input_hash,
    compute_input_manifest_hash,
    compute_skill_fingerprint,
)
from ..services.orchestration.run_store import run_store
from ..services.orchestration.run_audit_contract_service import run_audit_contract_service
from ..services.orchestration.run_service_log_mirror import RunServiceLogMirrorSession
from ..services.orchestration.run_skill_materialization_service import run_folder_bootstrapper
from ..services.orchestration.run_state_service import run_state_service
from ..services.skill.temp_skill_run_manager import temp_skill_run_manager
from ..services.skill.temp_skill_run_store import temp_skill_run_store
from ..services.orchestration.workspace_manager import workspace_manager
from ..services.engine_management.engine_policy import resolve_skill_engine_policy
from ..services.orchestration.run_execution_core import (
    build_effective_runtime_options,
    declared_execution_modes,
    ensure_skill_engine_supported,
    ensure_skill_execution_mode_supported,
    is_cache_enabled,
    normalize_effective_runtime_policy,
    resolve_conversation_mode,
    validate_runtime_and_model_options,
)
from ..services.orchestration.run_interaction_service import run_interaction_service
from ..runtime.observability.run_read_facade import run_read_facade
from ..runtime.observability.run_source_adapter import RunSourceCapabilities
from ..runtime.logging.run_context import bind_run_logging_context


router = APIRouter(prefix="/temp-skill-runs", tags=["temp-skill-runs"])
logger = logging.getLogger(__name__)

install_runtime_protocol_ports()
install_runtime_observability_ports()


def _execution_mode_value(mode: object) -> str:
    value = getattr(mode, "value", mode)
    return str(value)


class _TempRouterSourceAdapter:
    source = "temp"
    cache_namespace = "temp_cache_entries"
    capabilities = RunSourceCapabilities(
        supports_pending_reply=True,
        supports_event_history=True,
        supports_log_range=True,
        supports_inline_input_create=False,
    )

    async def get_request(self, request_id: str):
        return await maybe_await(temp_skill_run_store.get_request(request_id))

    async def get_cached_run(self, cache_key: str):
        return await maybe_await(run_store.get_temp_cached_run(cache_key))

    async def bind_cached_run(self, request_id: str, run_id: str) -> None:
        await maybe_await(temp_skill_run_store.bind_cached_run(request_id, run_id))
        if await maybe_await(run_store.get_request(request_id)):
            await maybe_await(run_store.bind_request_run_id(request_id, run_id, status=RunStatus.SUCCEEDED.value))

    async def mark_run_started(self, request_id: str, run_id: str) -> None:
        await maybe_await(temp_skill_run_store.update_run_started(request_id, run_id))
        if await maybe_await(run_store.get_request(request_id)):
            await maybe_await(run_store.bind_request_run_id(request_id, run_id, status=RunStatus.QUEUED.value))

    async def mark_failed(self, request_id: str, error_message: str) -> None:
        await maybe_await(temp_skill_run_store.update_status(
            request_id=request_id,
            status=RunStatus.FAILED,
            error=error_message,
        ))

    def get_run_job_temp_request_id(self, request_id: str) -> str | None:
        return request_id

    def build_cancel_kwargs(self, request_id: str) -> dict[str, str]:
        return {"request_id": request_id, "temp_request_id": request_id}


temp_source_adapter = _TempRouterSourceAdapter()


@router.post("", response_model=TempSkillRunCreateResponse)
async def create_temp_skill_run(request: TempSkillRunCreateRequest):
    try:
        runtime_opts, engine_opts = validate_runtime_and_model_options(
            engine=request.engine,
            model=request.model,
            runtime_options=request.runtime_options,
        )
        client_metadata = request.client_metadata.model_dump(mode="json")

        request_id = str(uuid.uuid4())
        request_payload = {
            "skill_id": "__temporary__",
            "engine": request.engine,
            "parameter": request.parameter,
            "model": request.model,
            "engine_options": engine_opts,
            "runtime_options": runtime_opts,
            "client_metadata": client_metadata,
            "effective_runtime_options": runtime_opts,
        }
        workspace_manager.create_request(request_id, request_payload)
        temp_skill_run_manager.create_request_dirs(request_id)
        await temp_skill_run_store.create_request(
            request_id=request_id,
            engine=request.engine,
            parameter=request.parameter,
            model=request.model,
            engine_options=engine_opts,
            runtime_options=runtime_opts,
            effective_runtime_options=runtime_opts,
            client_metadata=client_metadata,
        )
        return TempSkillRunCreateResponse(request_id=request_id, status=RunStatus.QUEUED)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        # Router boundary mapping: preserve HTTP 500 contract for unclassified errors.
        logger.exception(
            "temp_skill_runs.create failed; returning HTTP 500",
            extra={
                "component": "router.temp_skill_runs",
                "action": "create_temp_skill_run",
                "error_type": type(exc).__name__,
                "fallback": "http_500",
            },
        )
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{request_id}/upload", response_model=TempSkillRunUploadResponse)
async def upload_temp_skill_and_start(
    request_id: str,
    background_tasks: BackgroundTasks,
    skill_package: UploadFile = File(...),
    file: UploadFile | None = File(default=None),
):
    record = await temp_skill_run_store.get_request(request_id)
    if not record:
        raise HTTPException(status_code=404, detail="Request not found")
    if record.get("run_id"):
        raise HTTPException(status_code=400, detail="Run already started")

    run_status = None
    extracted_files: list[str] = []
    try:
        skill_bytes = await skill_package.read()
        skill_package_hash = compute_bytes_hash(skill_bytes)
        inspected_skill = await temp_skill_run_manager.inspect_skill_package(request_id, skill_bytes)
        engine_policy = resolve_skill_engine_policy(inspected_skill)
        ensure_skill_engine_supported(
            skill_id=inspected_skill.id,
            requested_engine=record["engine"],
            policy=engine_policy,
        )
        client_metadata = record.get("client_metadata", {})
        policy = normalize_effective_runtime_policy(
            declared_modes=declared_execution_modes(inspected_skill),
            runtime_options=record.get("runtime_options", {}),
            client_metadata=client_metadata,
        )
        effective_runtime_options = build_effective_runtime_options(
            runtime_options=record.get("runtime_options", {}),
            policy=policy,
        )
        ensure_skill_execution_mode_supported(
            skill_id=inspected_skill.id,
            requested_mode=policy.effective_execution_mode,
            declared_modes=declared_execution_modes(inspected_skill),
        )
        record["effective_runtime_options"] = effective_runtime_options
        await temp_skill_run_store.update_effective_runtime(
            request_id,
            effective_runtime_options=effective_runtime_options,
            client_metadata=client_metadata,
        )

        if file is not None:
            input_bytes = await file.read()
            upload_res = workspace_manager.handle_upload(request_id, input_bytes)
            extracted_files = upload_res.get("extracted_files", [])

        runtime_options = record.get("runtime_options", {})
        cache_enabled = is_cache_enabled(effective_runtime_options)
        await _ensure_temp_request_synced_in_run_store(
            request_id=request_id,
            temp_record=record,
            skill_id=inspected_skill.id,
        )
        manifest_path = workspace_manager.write_input_manifest(request_id)
        manifest_hash = compute_input_manifest_hash(
            json.loads(manifest_path.read_text(encoding="utf-8"))
        )
        await run_store.update_request_manifest(request_id, str(manifest_path), manifest_hash)
        skill_fingerprint = compute_skill_fingerprint(inspected_skill, record["engine"])
        cache_key = compute_cache_key(
            skill_id=inspected_skill.id,
            engine=record["engine"],
            skill_fingerprint=skill_fingerprint,
            parameter=record["parameter"],
            engine_options=record["engine_options"],
            input_manifest_hash=manifest_hash,
            inline_input_hash=compute_inline_input_hash({}),
            temp_skill_package_hash=skill_package_hash,
        )
        await run_store.update_request_cache_key(request_id, cache_key, skill_fingerprint)
        if cache_enabled:
            cached_run = await temp_source_adapter.get_cached_run(cache_key)
            if cached_run:
                await temp_source_adapter.bind_cached_run(request_id, cached_run)
                await temp_skill_run_manager.cleanup_temp_assets(request_id)
                await temp_skill_run_manager.on_terminal(
                    request_id,
                    RunStatus.SUCCEEDED,
                    debug_keep_temp=bool(runtime_options.get("debug_keep_temp")),
                )
                return TempSkillRunUploadResponse(
                    request_id=request_id,
                    cache_hit=True,
                    status=RunStatus.SUCCEEDED,
                    extracted_files=extracted_files,
                )

        run_request = RunCreateRequest(
            skill_id=inspected_skill.id,
            engine=record["engine"],
            parameter=record["parameter"],
            model=record.get("model"),
            runtime_options=effective_runtime_options,
            client_metadata=record.get("client_metadata", {}),
        )
        run_status = workspace_manager.create_run_for_skill(run_request, inspected_skill)
        workspace_manager.promote_request_uploads(request_id, run_status.run_id)
        run_cache_key: str | None = cache_key if cache_enabled else None
        await run_store.create_run(run_status.run_id, run_cache_key, RunStatus.QUEUED)
        await temp_source_adapter.mark_run_started(request_id, run_status.run_id)
        request_record = await maybe_await(run_store.get_request(request_id))
        run_dir = workspace_manager.get_run_dir(run_status.run_id)
        if run_dir is None:
            raise HTTPException(status_code=500, detail="Run directory not found")
        run_audit_contract_service.initialize_run_audit(run_dir=run_dir)
        with contextlib.ExitStack() as run_log_stack:
            run_log_stack.enter_context(
                bind_run_logging_context(
                    run_id=run_status.run_id,
                    request_id=request_id,
                    attempt_number=None,
                )
            )
            run_log_stack.enter_context(
                RunServiceLogMirrorSession.open_run_scope(
                    run_dir=run_dir,
                    run_id=run_status.run_id,
                )
            )
            logger.info(
                "temp_run_create_orchestration_begin run_id=%s request_id=%s engine=%s",
                run_status.run_id,
                request_id,
                record["engine"],
            )
            run_audit_contract_service.write_request_input_snapshot(
                run_dir=run_dir,
                request_payload=request_record or record,
            )
            skill, _skill_ref = run_folder_bootstrapper.materialize_temp_skill_package(
                package_bytes=skill_bytes,
                run_dir=run_dir,
                engine_name=record["engine"],
                execution_mode=_execution_mode_value(policy.effective_execution_mode),
                source=RunLocalSkillSource.TEMP_UPLOAD,
            )
            await temp_skill_run_manager.cleanup_temp_assets(request_id)
            await run_state_service.initialize_queued_state(
                run_dir=run_dir,
                request_id=request_id,
                run_id=run_status.run_id,
                request_record=request_record,
                run_store_backend=run_store,
            )

            merged_options = {**record["engine_options"], **effective_runtime_options}
            admitted = await concurrency_manager.admit_or_reject()
            if not admitted:
                raise HTTPException(status_code=429, detail="Job queue is full")
            await run_state_service.advance_dispatch_phase(
                run_dir=run_dir,
                request_id=request_id,
                run_id=run_status.run_id,
                phase=DispatchPhase.ADMITTED,
                run_store_backend=run_store,
            )
            await run_state_service.advance_dispatch_phase(
                run_dir=run_dir,
                request_id=request_id,
                run_id=run_status.run_id,
                phase=DispatchPhase.DISPATCH_SCHEDULED,
                run_store_backend=run_store,
            )
            logger.info(
                "temp_run_create_orchestration_ready run_id=%s request_id=%s engine=%s",
                run_status.run_id,
                request_id,
                record["engine"],
            )
        background_tasks.add_task(
            job_orchestrator.run_job,
            run_id=run_status.run_id,
            skill_id=skill.id,
            engine_name=record["engine"],
            options=merged_options,
            cache_key=run_cache_key,
            temp_request_id=request_id,
        )
        return TempSkillRunUploadResponse(
            request_id=request_id,
            cache_hit=False,
            status=run_status.status,
            extracted_files=extracted_files,
        )
    except HTTPException as exc:
        detail = exc.detail
        if isinstance(detail, dict):
            error_message = detail.get("message") or detail.get("code") or str(detail)
        else:
            error_message = str(detail)
        if run_status is not None:
            await temp_skill_run_store.update_status(request_id, RunStatus.FAILED, error=error_message)
        elif record.get("run_id") is None:
            await temp_skill_run_store.update_status(request_id, RunStatus.FAILED, error=error_message)
        raise
    except ValueError as exc:
        await temp_skill_run_store.update_status(request_id, RunStatus.FAILED, error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        # Router boundary mapping: preserve HTTP 500 contract for unclassified errors.
        logger.exception(
            "temp_skill_runs.upload failed; returning HTTP 500",
            extra={
                "component": "router.temp_skill_runs",
                "action": "upload_temp_skill_and_start",
                "error_type": type(exc).__name__,
                "fallback": "http_500_after_status_update",
            },
        )
        await temp_skill_run_store.update_status(request_id, RunStatus.FAILED, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{request_id}", response_model=RequestStatusResponse)
async def get_temp_skill_run_status(request_id: str):
    rec = await temp_skill_run_store.get_request(request_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Request not found")
    runtime_options = rec.get("runtime_options", {})
    effective_runtime_options = rec.get("effective_runtime_options", runtime_options)
    runtime_policy_fields = _build_runtime_policy_fields(
        runtime_options=runtime_options,
        effective_runtime_options=effective_runtime_options,
        client_metadata=rec.get("client_metadata"),
    )

    created_at = _parse_dt(rec.get("created_at"))
    updated_at = _parse_dt(rec.get("updated_at"))
    run_id = rec.get("run_id")

    if not run_id:
        auto_stats = await run_store.get_auto_decision_stats(request_id)
        return RequestStatusResponse(
            request_id=request_id,
            status=RunStatus(rec.get("status", RunStatus.QUEUED.value)),
            skill_id=rec.get("skill_id") or "unknown",
            engine=rec.get("engine", "unknown"),
            created_at=created_at,
            updated_at=updated_at,
            warnings=[],
            error={"message": rec["error"]} if rec.get("error") else None,
            auto_decision_count=int(auto_stats.get("auto_decision_count") or 0),
            last_auto_decision_at=_parse_optional_dt(auto_stats.get("last_auto_decision_at")),
            pending_interaction_id=None,
            interaction_count=await run_store.get_interaction_count(request_id),
            recovery_state=RecoveryState.NONE,
            recovered_at=None,
            recovery_reason=None,
            requested_execution_mode=runtime_policy_fields["requested_execution_mode"],
            effective_execution_mode=runtime_policy_fields["effective_execution_mode"],
            conversation_mode=runtime_policy_fields["conversation_mode"],
            interactive_auto_reply=runtime_policy_fields["interactive_auto_reply"],
            interactive_reply_timeout_sec=runtime_policy_fields["interactive_reply_timeout_sec"],
            effective_interactive_require_user_reply=runtime_policy_fields["effective_interactive_require_user_reply"],
            effective_interactive_reply_timeout_sec=runtime_policy_fields["effective_interactive_reply_timeout_sec"],
        )

    run_dir = workspace_manager.get_run_dir(run_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run not found")

    projection_payload = await run_store.get_current_projection(request_id)
    state_payload = await run_store.get_run_state(request_id)
    dispatch_payload = await run_store.get_dispatch_state(request_id)
    status_file = run_dir / ".state" / "state.json"
    status = RunStatus(rec.get("status", RunStatus.QUEUED.value))
    warnings: list[Any] = []
    error = {"message": rec["error"]} if rec.get("error") else None
    if isinstance(state_payload, dict):
        status = RunStatus(state_payload.get("status", RunStatus.QUEUED.value))
        warnings = state_payload.get("warnings", [])
        error = state_payload.get("error")
        updated_at = _parse_dt(state_payload.get("updated_at"))
    elif isinstance(projection_payload, dict):
        status = RunStatus(projection_payload.get("status", RunStatus.QUEUED.value))
        warnings = projection_payload.get("warnings", [])
        error = projection_payload.get("error")
        updated_at = _parse_dt(projection_payload.get("updated_at"))
    elif status_file.exists():
        payload = json.loads(status_file.read_text(encoding="utf-8"))
        status = RunStatus(payload.get("status", RunStatus.QUEUED.value))
        warnings = payload.get("warnings", [])
        error = payload.get("error")
        updated_at = _parse_dt(payload.get("updated_at"))
    record_status = rec.get("status")
    if status == RunStatus.QUEUED and isinstance(record_status, str):
        parsed_record_status = RunStatus(record_status)
        if parsed_record_status in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED}:
            status = parsed_record_status
            if rec.get("error"):
                error = {"message": rec["error"]}
    recovery_info = await run_store.get_recovery_info(run_id)
    recovered_at_raw = recovery_info.get("recovered_at")
    recovered_at = _parse_dt(recovered_at_raw) if recovered_at_raw else None
    auto_stats = await run_store.get_auto_decision_stats(request_id)
    pending_interaction_id = (
        state_payload.get("pending", {}).get("interaction_id")
        if isinstance(state_payload, dict)
        and isinstance(state_payload.get("pending"), dict)
        and state_payload.get("pending", {}).get("interaction_id") is not None
        else (
            projection_payload.get("pending_interaction_id")
            if isinstance(projection_payload, dict) and projection_payload.get("pending_interaction_id") is not None
            else (
                await _read_pending_interaction_id(request_id)
                if status == RunStatus.WAITING_USER
                else None
            )
        )
    )

    return RequestStatusResponse(
        request_id=request_id,
        status=status,
        skill_id=rec.get("skill_id") or "unknown",
        engine=rec.get("engine", "unknown"),
        created_at=created_at,
        updated_at=updated_at,
        warnings=warnings,
        error=error,
        auto_decision_count=int(auto_stats.get("auto_decision_count") or 0),
        last_auto_decision_at=_parse_optional_dt(auto_stats.get("last_auto_decision_at")),
        pending_interaction_id=pending_interaction_id,
        interaction_count=await run_store.get_interaction_count(request_id),
        recovery_state=_parse_recovery_state(recovery_info.get("recovery_state")),
        recovered_at=recovered_at,
        recovery_reason=_coerce_str_or_none(recovery_info.get("recovery_reason")),
        requested_execution_mode=runtime_policy_fields["requested_execution_mode"],
        effective_execution_mode=runtime_policy_fields["effective_execution_mode"],
        conversation_mode=runtime_policy_fields["conversation_mode"],
        interactive_auto_reply=runtime_policy_fields["interactive_auto_reply"],
        interactive_reply_timeout_sec=runtime_policy_fields["interactive_reply_timeout_sec"],
        effective_interactive_require_user_reply=runtime_policy_fields["effective_interactive_require_user_reply"],
        effective_interactive_reply_timeout_sec=runtime_policy_fields["effective_interactive_reply_timeout_sec"],
        current_attempt=_coerce_optional_positive_int(
            (
                state_payload.get("current_attempt")
                if isinstance(state_payload, dict)
                else projection_payload.get("current_attempt") if isinstance(projection_payload, dict) else None
            )
        ),
        pending_owner=(
            _coerce_pending_owner(
                state_payload.get("pending", {}).get("owner")
                if isinstance(state_payload, dict) and isinstance(state_payload.get("pending"), dict)
                else projection_payload.get("pending_owner") if isinstance(projection_payload, dict) else None
            )
        ),
        pending_payload=(
            state_payload.get("pending", {}).get("payload")
            if isinstance(state_payload, dict) and isinstance(state_payload.get("pending"), dict)
            else None
        ),
        dispatch_phase=(
            DispatchPhase(dispatch_payload.get("phase"))
            if isinstance(dispatch_payload, dict) and isinstance(dispatch_payload.get("phase"), str)
            else None
        ),
        dispatch_ticket_id=(
            _coerce_str_or_none(dispatch_payload.get("dispatch_ticket_id"))
            if isinstance(dispatch_payload, dict)
            else None
        ),
        worker_claim_id=(
            _coerce_str_or_none(dispatch_payload.get("worker_claim_id"))
            if isinstance(dispatch_payload, dict)
            else None
        ),
        resume_ticket_id=(
            _coerce_str_or_none(
                state_payload.get("resume", {}).get("resume_ticket_id")
                if isinstance(state_payload, dict) and isinstance(state_payload.get("resume"), dict)
                else projection_payload.get("resume_ticket_id") if isinstance(projection_payload, dict) else None
            )
        ),
        resume_cause=(
            _coerce_resume_cause(
                state_payload.get("resume", {}).get("resume_cause")
                if isinstance(state_payload, dict) and isinstance(state_payload.get("resume"), dict)
                else projection_payload.get("resume_cause") if isinstance(projection_payload, dict) else None
            )
        ),
        source_attempt=_coerce_optional_positive_int(
            (
                state_payload.get("resume", {}).get("source_attempt")
                if isinstance(state_payload, dict) and isinstance(state_payload.get("resume"), dict)
                else projection_payload.get("source_attempt") if isinstance(projection_payload, dict) else None
            )
        ),
        target_attempt=_coerce_optional_positive_int(
            (
                state_payload.get("resume", {}).get("target_attempt")
                if isinstance(state_payload, dict) and isinstance(state_payload.get("resume"), dict)
                else projection_payload.get("target_attempt") if isinstance(projection_payload, dict) else None
            )
        ),
    )


@router.get("/{request_id}/result", response_model=RunResultResponse)
async def get_temp_skill_run_result(request_id: str):
    return await run_read_facade.get_result(
        source_adapter=temp_source_adapter,
        request_id=request_id,
    )


@router.get("/{request_id}/artifacts", response_model=RunArtifactsResponse)
async def get_temp_skill_run_artifacts(request_id: str):
    return await run_read_facade.get_artifacts(
        source_adapter=temp_source_adapter,
        request_id=request_id,
    )


@router.get("/{request_id}/bundle")
async def get_temp_skill_run_bundle(request_id: str):
    return await run_read_facade.get_bundle(
        source_adapter=temp_source_adapter,
        request_id=request_id,
    )


@router.get("/{request_id}/artifacts/{artifact_path:path}")
async def download_temp_skill_artifact(request_id: str, artifact_path: str):
    return await run_read_facade.get_artifact_file(
        source_adapter=temp_source_adapter,
        request_id=request_id,
        artifact_path=artifact_path,
    )


@router.get("/{request_id}/logs", response_model=RunLogsResponse)
async def get_temp_skill_run_logs(request_id: str):
    return await run_read_facade.get_logs(
        source_adapter=temp_source_adapter,
        request_id=request_id,
    )


@router.post("/{request_id}/cancel", response_model=CancelResponse)
async def cancel_temp_skill_run(request_id: str):
    return await run_read_facade.cancel_run(
        source_adapter=temp_source_adapter,
        request_id=request_id,
    )


@router.get("/{request_id}/events")
async def stream_temp_skill_run_events(
    request_id: str,
    request: Request,
    cursor: int = Query(default=0, ge=0),
):
    return await run_read_facade.stream_events(
        source_adapter=temp_source_adapter,
        request_id=request_id,
        request=request,
        cursor=cursor,
    )


@router.get("/{request_id}/events/history")
async def list_temp_skill_run_event_history(
    request_id: str,
    from_seq: int | None = Query(default=None, ge=0),
    to_seq: int | None = Query(default=None, ge=0),
    from_ts: str | None = Query(default=None),
    to_ts: str | None = Query(default=None),
):
    return await run_read_facade.list_event_history(
        source_adapter=temp_source_adapter,
        request_id=request_id,
        from_seq=from_seq,
        to_seq=to_seq,
        from_ts=from_ts,
        to_ts=to_ts,
    )


@router.get("/{request_id}/chat")
async def stream_temp_skill_run_chat(
    request_id: str,
    request: Request,
    cursor: int = Query(default=0, ge=0),
):
    return await run_read_facade.stream_chat(
        source_adapter=temp_source_adapter,
        request_id=request_id,
        request=request,
        cursor=cursor,
    )


@router.get("/{request_id}/chat/history")
async def list_temp_skill_run_chat_history(
    request_id: str,
    from_seq: int | None = Query(default=None, ge=0),
    to_seq: int | None = Query(default=None, ge=0),
    from_ts: str | None = Query(default=None),
    to_ts: str | None = Query(default=None),
):
    return await run_read_facade.list_chat_history(
        source_adapter=temp_source_adapter,
        request_id=request_id,
        from_seq=from_seq,
        to_seq=to_seq,
        from_ts=from_ts,
        to_ts=to_ts,
    )


@router.get("/{request_id}/logs/range")
async def get_temp_skill_run_log_range(
    request_id: str,
    stream: str = Query(...),
    byte_from: int = Query(default=0, ge=0),
    byte_to: int = Query(default=0, ge=0),
    attempt: int | None = Query(default=None, ge=1),
):
    return await run_read_facade.read_log_range(
        source_adapter=temp_source_adapter,
        request_id=request_id,
        stream=stream,
        byte_from=byte_from,
        byte_to=byte_to,
        attempt=attempt,
    )


@router.get("/{request_id}/interaction/pending", response_model=InteractionPendingResponse)
async def get_temp_skill_interaction_pending(request_id: str):
    return await run_interaction_service.get_pending(
        source_adapter=temp_source_adapter,
        request_id=request_id,
        run_store_backend=run_store,
    )


@router.post("/{request_id}/interaction/reply", response_model=InteractionReplyResponse)
async def reply_temp_skill_interaction(
    request_id: str,
    request: InteractionReplyRequest,
    background_tasks: BackgroundTasks,
):
    return await run_interaction_service.submit_reply(
        source_adapter=temp_source_adapter,
        request_id=request_id,
        request=request,
        background_tasks=background_tasks,
        run_store_backend=run_store,
    )


@router.get("/{request_id}/auth/session", response_model=AuthSessionStatusResponse)
async def get_temp_skill_auth_session_status(request_id: str):
    return await run_interaction_service.get_auth_session_status(
        source_adapter=temp_source_adapter,
        request_id=request_id,
        run_store_backend=run_store,
    )


async def _ensure_temp_request_synced_in_run_store(
    *,
    request_id: str,
    temp_record: dict[str, Any],
    skill_id: str,
) -> None:
    if await run_store.get_request(request_id):
        return
    await run_store.create_request(
        request_id=request_id,
        skill_id=skill_id,
        engine=str(temp_record.get("engine", "")),
        input_data={},
        parameter=temp_record.get("parameter", {}),
        engine_options=temp_record.get("engine_options", {}),
        runtime_options=temp_record.get("runtime_options", {}),
        effective_runtime_options=temp_record.get("effective_runtime_options", temp_record.get("runtime_options", {})),
        client_metadata=temp_record.get("client_metadata", {}),
    )


async def _read_pending_interaction_id(request_id: str) -> int | None:
    pending = await maybe_await(run_store.get_pending_interaction(request_id))
    if not isinstance(pending, dict):
        return None
    value = pending.get("interaction_id")
    if value is None:
        return None
    try:
        interaction_id = int(value)
    except (TypeError, ValueError):
        return None
    if interaction_id <= 0:
        return None
    return interaction_id


def _parse_dt(raw: str | None) -> datetime:
    if not raw:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.utcnow()


def _parse_optional_dt(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _coerce_str_or_none(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        value = raw.strip()
        return value or None
    return str(raw)


def _coerce_optional_positive_int(raw: Any) -> int | None:
    return raw if isinstance(raw, int) and raw > 0 else None


def _coerce_pending_owner(raw: Any) -> PendingOwner | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return PendingOwner(raw)
    except ValueError:
        return None


def _coerce_resume_cause(raw: Any) -> ResumeCause | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return ResumeCause(raw)
    except ValueError:
        return None


def _resolve_interactive_autoreply_runtime_options(runtime_options: Any) -> tuple[bool | None, int | None]:
    if not isinstance(runtime_options, dict):
        return (None, None)
    auto_reply_obj = runtime_options.get("interactive_auto_reply")
    if not isinstance(auto_reply_obj, bool):
        return (None, None)
    timeout_obj = runtime_options.get("interactive_reply_timeout_sec")
    timeout_sec: int | None = None
    if isinstance(timeout_obj, int) and timeout_obj >= 0:
        timeout_sec = timeout_obj
    return (auto_reply_obj, timeout_sec)


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


def _build_runtime_policy_fields(
    *,
    runtime_options: Any,
    effective_runtime_options: Any,
    client_metadata: Any,
) -> dict[str, Any]:
    requested_mode = None
    if isinstance(runtime_options, dict):
        requested_mode = _coerce_execution_mode(
            runtime_options.get("execution_mode", ExecutionMode.AUTO.value)
        )
    effective_mode = None
    if isinstance(effective_runtime_options, dict):
        effective_mode = _coerce_execution_mode(
            effective_runtime_options.get("execution_mode", ExecutionMode.AUTO.value)
        )
    conversation_mode = _coerce_conversation_mode(resolve_conversation_mode(client_metadata))
    interactive_auto_reply, interactive_reply_timeout_sec = _resolve_interactive_autoreply_runtime_options(
        effective_runtime_options
    )
    return {
        "requested_execution_mode": requested_mode,
        "effective_execution_mode": effective_mode,
        "conversation_mode": conversation_mode,
        "interactive_auto_reply": interactive_auto_reply,
        "interactive_reply_timeout_sec": interactive_reply_timeout_sec,
        "effective_interactive_require_user_reply": bool(
            effective_mode == ExecutionMode.INTERACTIVE
            and conversation_mode == ClientConversationMode.SESSION
        ),
        "effective_interactive_reply_timeout_sec": interactive_reply_timeout_sec,
    }


def _parse_recovery_state(raw: Any) -> RecoveryState:
    if isinstance(raw, RecoveryState):
        return raw
    if isinstance(raw, str):
        try:
            return RecoveryState(raw)
        except ValueError:
            return RecoveryState.NONE
    return RecoveryState.NONE
