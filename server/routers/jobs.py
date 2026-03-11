"""
API Router for Job Management.

Exposes endpoints for:
- Creating new jobs (POST /jobs)
- Querying job status (GET /jobs/{request_id})
- Uploading files to a job workspace (POST /jobs/{request_id}/upload)
"""

import logging
import contextlib
import io
import shutil
import zipfile
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Form, Query, Request  # type: ignore[import-not-found]
from typing import Any
from ..config import config
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
    RunCreateRequest,
    RunCreateResponse,
    RunFilePreviewResponse,
    RunFilesResponse,
    RunUploadResponse,
    RequestStatusResponse,
    RequestSkillSource,
    RecoveryState,
    ResumeCause,
    RunLocalSkillSource,
    RunStatus,
    RunResultResponse,
    RunArtifactsResponse,
    RunLogsResponse,
    RunCleanupResponse
)
from ..services.orchestration.workspace_manager import workspace_manager
from ..services.skill.skill_registry import skill_registry
from ..services.orchestration.job_orchestrator import job_orchestrator
from ..services.orchestration.runtime_observability_ports import install_runtime_observability_ports
from ..services.orchestration.runtime_protocol_ports import install_runtime_protocol_ports
from ..services.platform.schema_validator import schema_validator
from ..services.skill.skill_asset_resolver import resolve_schema_asset
from ..services.engine_management.model_registry import model_registry
from ..services.platform.cache_key_builder import (
    build_input_manifest,
    compute_bytes_hash,
    compute_skill_fingerprint,
    compute_input_manifest_hash,
    compute_inline_input_hash,
    compute_cache_key,
)
from ..services.platform.async_compat import maybe_await
from ..services.orchestration.run_store import run_store
from ..services.orchestration.run_cleanup_manager import run_cleanup_manager
from ..services.orchestration.run_audit_contract_service import run_audit_contract_service
from ..services.orchestration.run_service_log_mirror import RunServiceLogMirrorSession
from ..services.orchestration.run_skill_materialization_service import run_folder_bootstrapper
from ..services.orchestration.run_state_service import run_state_service
from ..services.platform.concurrency_manager import concurrency_manager
from ..runtime.observability.run_observability import run_observability_service
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
from ..runtime.logging.run_context import bind_request_logging_context, bind_run_logging_context
from ..runtime.logging.structured_trace import log_event
import uuid
import json

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)

install_runtime_protocol_ports()
install_runtime_observability_ports()


def _parse_datetime_utc(raw: Any, *, default_now: bool = False) -> datetime | None:
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    if isinstance(raw, str) and raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc) if default_now else None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return datetime.now(timezone.utc) if default_now else None


def _execution_mode_value(mode: object) -> str:
    value = getattr(mode, "value", mode)
    return str(value)


def _extract_zip_to_dir(file_bytes: bytes, target_dir: Path) -> list[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            archive.extractall(target_dir)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid zip file") from exc
    return [str(p.relative_to(target_dir)) for p in target_dir.rglob("*") if p.is_file()]


def _copy_tree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for path in src.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())

@router.post("", response_model=RunCreateResponse)
async def create_run(request: RunCreateRequest, background_tasks: BackgroundTasks):
    try:
        skill = None
        if request.skill_source == RequestSkillSource.INSTALLED:
            if not request.skill_id:
                raise HTTPException(status_code=422, detail="skill_id is required for installed source")
            skill = skill_registry.get_skill(request.skill_id)
            if not skill:
                raise HTTPException(status_code=404, detail=f"Skill '{request.skill_id}' not found")

        if request.skill_source == RequestSkillSource.TEMP_UPLOAD and request.skill_id:
            raise HTTPException(status_code=422, detail="skill_id must be empty for temp_upload source")

        if skill is not None:
            engine_policy = resolve_skill_engine_policy(skill)
            ensure_skill_engine_supported(
                skill_id=skill.id,
                requested_engine=request.engine,
                policy=engine_policy,
            )
        runtime_opts, engine_opts = validate_runtime_and_model_options(
            engine=request.engine,
            model=request.model,
            runtime_options=request.runtime_options,
        )
        client_metadata = request.client_metadata.model_dump(mode="json")
        declared_modes = declared_execution_modes(skill) if skill is not None else [ExecutionMode.AUTO.value]
        policy = normalize_effective_runtime_policy(
            declared_modes=declared_modes,
            runtime_options=runtime_opts,
            client_metadata=client_metadata,
        )
        effective_runtime_opts = build_effective_runtime_options(
            runtime_options=runtime_opts,
            policy=policy,
        )
        if skill is not None:
            ensure_skill_execution_mode_supported(
                skill_id=skill.id,
                requested_mode=policy.effective_execution_mode,
                declared_modes=declared_execution_modes(skill),
            )

        request_id = str(uuid.uuid4())
        inline_input = request.input if isinstance(request.input, dict) else {}
        inline_input_hash = compute_inline_input_hash(inline_input)
        if skill is not None:
            inline_input_errors = schema_validator.validate_inline_input_create(skill, inline_input)
            if inline_input_errors:
                raise HTTPException(status_code=400, detail=f"Input validation failed: {inline_input_errors}")

        request_payload = request.model_dump()
        request_payload["engine_options"] = engine_opts
        request_payload["runtime_options"] = runtime_opts
        request_payload["effective_runtime_options"] = effective_runtime_opts

        declared_file_input_present = False
        has_required_file_inputs = False
        if skill and resolve_schema_asset(skill, "input").path is not None:
            file_keys = set(schema_validator.get_input_keys_by_source(skill, "file"))
            has_required_file_inputs = bool(
                schema_validator.has_required_file_inputs(skill)
            )
            declared_file_input_present = any(
                key in inline_input for key in file_keys
            )
        requires_upload = (
            request.skill_source == RequestSkillSource.TEMP_UPLOAD
            or has_required_file_inputs
            or declared_file_input_present
        )

        await run_store.create_request(
            request_id=request_id,
            skill_id=(skill.id if skill is not None else "__temp_upload__"),
            engine=request.engine,
            input_data=inline_input,
            parameter=request.parameter,
            engine_options=engine_opts,
            runtime_options=runtime_opts,
            effective_runtime_options=effective_runtime_opts,
            client_metadata=client_metadata,
            skill_source=request.skill_source.value,
            request_upload_mode=("pending_upload" if requires_upload else "none"),
        )

        cache_enabled = is_cache_enabled(effective_runtime_opts)
        if requires_upload:
            return RunCreateResponse(
                request_id=request_id,
                cache_hit=False,
                status=None,
            )

        if skill is None:
            raise HTTPException(status_code=500, detail="temp_upload request must go through upload flow")

        manifest_hash = compute_input_manifest_hash({"files": []})
        skill_fingerprint = compute_skill_fingerprint(skill, request.engine)
        cache_key = compute_cache_key(
            skill_id=skill.id,
            engine=request.engine,
            skill_fingerprint=skill_fingerprint,
            parameter=request.parameter,
            engine_options=engine_opts,
            input_manifest_hash=manifest_hash,
            inline_input_hash=inline_input_hash,
        )
        await run_store.update_request_manifest(
            request_id,
            None,
            manifest_hash,
            request_upload_mode="uploaded",
        )
        await run_store.update_request_cache_key(request_id, cache_key, skill_fingerprint)
        if cache_enabled:
            cached_run = await run_store.get_cached_run_for_source(cache_key, request.skill_source.value)
            if cached_run:
                await run_store.bind_request_run_id(
                    request_id,
                    cached_run,
                    status=RunStatus.SUCCEEDED.value,
                )
                return RunCreateResponse(
                    request_id=request_id,
                    cache_hit=True,
                    status=RunStatus.SUCCEEDED,
                )

        run_request = RunCreateRequest(
            skill_source=RequestSkillSource.INSTALLED,
            skill_id=skill.id,
            engine=request.engine,
            input=inline_input,
            parameter=request.parameter,
            model=request.model,
            runtime_options=effective_runtime_opts,
            client_metadata=request.client_metadata,
        )
        run_status = workspace_manager.create_run(run_request)
        run_cache_key: str | None = cache_key if cache_enabled else None
        await run_store.create_run(run_status.run_id, run_cache_key, RunStatus.QUEUED)
        await run_store.bind_request_run_id(
            request_id,
            run_status.run_id,
            status=RunStatus.QUEUED.value,
        )
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
                "run_create_orchestration_begin run_id=%s request_id=%s engine=%s",
                run_status.run_id,
                request_id,
                request.engine,
            )
            run_audit_contract_service.write_request_input_snapshot(
                run_dir=run_dir,
                request_payload=request_payload,
            )
            run_folder_bootstrapper.materialize_skill(
                skill=skill,
                run_dir=run_dir,
                engine_name=request.engine,
                execution_mode=_execution_mode_value(policy.effective_execution_mode),
                source=RunLocalSkillSource.INSTALLED,
            )
            await run_state_service.initialize_queued_state(
                run_dir=run_dir,
                request_id=request_id,
                run_id=run_status.run_id,
                request_record=request_record,
                run_store_backend=run_store,
            )
            merged_options = {**engine_opts, **effective_runtime_opts}
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
                "run_create_orchestration_ready run_id=%s request_id=%s engine=%s",
                run_status.run_id,
                request_id,
                request.engine,
            )
        background_tasks.add_task(
            job_orchestrator.run_job,
            run_id=run_status.run_id,
            skill_id=skill.id,
            engine_name=request.engine,
            options=merged_options,
            cache_key=run_cache_key
        )
        return RunCreateResponse(
            request_id=request_id,
            cache_hit=False,
            status=run_status.status
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        # Router boundary mapping: preserve HTTP 500 contract for unclassified errors.
        logger.exception(
            "jobs.create_run failed; returning HTTP 500",
            extra={
                "component": "router.jobs",
                "action": "create_run",
                "error_type": type(e).__name__,
                "fallback": "http_500",
            },
        )
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{request_id}", response_model=RequestStatusResponse)
async def get_run_status(request_id: str):
    request_record = await maybe_await(run_store.get_request(request_id))
    if not request_record:
        raise HTTPException(status_code=404, detail="Request not found")
    run_id = request_record.get("run_id")
    if not run_id:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = workspace_manager.get_run_dir(run_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run not found")
    
    
    projection_payload = await maybe_await(run_store.get_current_projection(request_id))
    state_payload = await maybe_await(run_store.get_run_state(request_id))
    dispatch_payload = await maybe_await(run_store.get_dispatch_state(request_id))
    status_file = run_dir / ".state" / "state.json"

    current_status = RunStatus.QUEUED
    warnings = []
    error = None
    updated_at = None
    if isinstance(state_payload, dict):
        current_status = RunStatus(state_payload.get("status", RunStatus.QUEUED.value))
        warnings = state_payload.get("warnings", [])
        error = state_payload.get("error")
        updated_at = state_payload.get("updated_at")
    elif isinstance(projection_payload, dict):
        current_status = RunStatus(projection_payload.get("status", RunStatus.QUEUED.value))
        warnings = projection_payload.get("warnings", [])
        error = projection_payload.get("error")
        updated_at = projection_payload.get("updated_at")
    elif status_file.exists():
        import json
        with open(status_file, 'r') as f:
            data = json.load(f)
            current_status = data.get("status", RunStatus.QUEUED)
            warnings = data.get("warnings", [])
            error = data.get("error")
            updated_at = data.get("updated_at")
    if current_status == RunStatus.WAITING_AUTH:
        from ..services.orchestration.run_auth_orchestration_service import (
            run_auth_orchestration_service,
        )

        with contextlib.ExitStack() as run_log_stack:
            run_log_stack.enter_context(
                bind_run_logging_context(
                    run_id=str(run_id),
                    request_id=request_id,
                    attempt_number=None,
                )
            )
            run_log_stack.enter_context(
                RunServiceLogMirrorSession.open_run_scope(
                    run_dir=run_dir,
                    run_id=str(run_id),
                )
            )
            logger.info(
                "run_status_waiting_auth_reconcile run_id=%s request_id=%s",
                run_id,
                request_id,
            )
            await run_auth_orchestration_service.reconcile_waiting_auth(request_id=request_id)
        projection_payload = await maybe_await(run_store.get_current_projection(request_id))
        state_payload = await maybe_await(run_store.get_run_state(request_id))
        dispatch_payload = await maybe_await(run_store.get_dispatch_state(request_id))
        if status_file.exists():
            import json
            with open(status_file, 'r') as f:
                data = json.load(f)
                current_status = data.get("status", RunStatus.QUEUED)
                warnings = data.get("warnings", [])
                error = data.get("error")
                updated_at = data.get("updated_at")
            
    # Read run metadata
    skill_id = str(request_record.get("skill_id") or "unknown")
    engine = str(request_record.get("engine") or "unknown")
    engine_options_obj = request_record.get("engine_options")
    engine_options = engine_options_obj if isinstance(engine_options_obj, dict) else {}
    model_obj = engine_options.get("model")
    if not isinstance(model_obj, str) or not model_obj.strip():
        model_obj = engine_options.get("model_id")
    model = model_obj.strip() if isinstance(model_obj, str) and model_obj.strip() else None
    
    # Return status
    created_at = datetime.now(timezone.utc)
    created_at_obj = request_record.get("created_at")
    parsed_created_at = _parse_datetime_utc(created_at_obj)
    if parsed_created_at is not None:
        created_at = parsed_created_at
    updated_at_dt = _parse_datetime_utc(updated_at, default_now=True) or datetime.now(timezone.utc)
    auto_stats = await maybe_await(run_store.get_auto_decision_stats(request_id))
    last_auto_decision_at_obj = auto_stats.get("last_auto_decision_at")
    last_auto_decision_at = _parse_datetime_utc(last_auto_decision_at_obj)
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
                if current_status == RunStatus.WAITING_USER
                else None
            )
        )
    )
    pending_auth_session_id = (
        state_payload.get("pending", {}).get("auth_session_id")
        if isinstance(state_payload, dict)
        and isinstance(state_payload.get("pending"), dict)
        and state_payload.get("pending", {}).get("auth_session_id") is not None
        else (
            projection_payload.get("pending_auth_session_id")
            if isinstance(projection_payload, dict) and projection_payload.get("pending_auth_session_id") is not None
            else (
                await _read_pending_auth_session_id(request_id)
                if current_status == RunStatus.WAITING_AUTH
                else None
            )
        )
    )
    runtime_options = request_record.get("runtime_options", {})
    effective_runtime_options = request_record.get("effective_runtime_options", runtime_options)
    runtime_policy_fields = _build_runtime_policy_fields(
        runtime_options=runtime_options,
        effective_runtime_options=effective_runtime_options,
        client_metadata=request_record.get("client_metadata"),
    )
    interaction_count = await maybe_await(run_store.get_interaction_count(request_id))
    recovery_info = await maybe_await(run_store.get_recovery_info(run_id))
    recovered_at = _parse_datetime_utc(recovery_info.get("recovered_at"))

    return RequestStatusResponse(
        request_id=request_id,
        status=current_status, 
        skill_id=skill_id,
        engine=engine,
        model=model,
        created_at=created_at,
        updated_at=updated_at_dt,
        warnings=warnings,
        error=error,
        auto_decision_count=int(auto_stats.get("auto_decision_count") or 0),
        last_auto_decision_at=last_auto_decision_at,
        pending_interaction_id=pending_interaction_id,
        pending_auth_session_id=pending_auth_session_id,
        interaction_count=interaction_count,
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
async def get_run_result(request_id: str):
    return await run_read_facade.get_result(request_id=request_id)

@router.get("/{request_id}/artifacts", response_model=RunArtifactsResponse)
async def get_run_artifacts(request_id: str):
    return await run_read_facade.get_artifacts(request_id=request_id)

@router.get("/{request_id}/bundle")
async def get_run_bundle(request_id: str):
    return await run_read_facade.get_bundle(request_id=request_id)


@router.get("/{request_id}/bundle/debug")
async def get_run_debug_bundle(request_id: str):
    return await run_read_facade.get_debug_bundle(request_id=request_id)


@router.get("/{request_id}/files", response_model=RunFilesResponse)
async def get_run_files(request_id: str):
    return await run_read_facade.get_files(request_id=request_id)


@router.get("/{request_id}/file", response_model=RunFilePreviewResponse)
async def get_run_file(
    request_id: str,
    path: str = Query(..., min_length=1),
):
    return await run_read_facade.get_file_preview(
        request_id=request_id,
        path=path,
    )

@router.get("/{request_id}/logs", response_model=RunLogsResponse)
async def get_run_logs(request_id: str):
    return await run_read_facade.get_logs(request_id=request_id)


@router.post("/{request_id}/cancel", response_model=CancelResponse)
async def cancel_run(request_id: str):
    return await run_read_facade.cancel_run(request_id=request_id)


@router.get("/{request_id}/events")
async def stream_run_events(
    request_id: str,
    request: Request,
    cursor: int = Query(default=0, ge=0),
):
    return await run_read_facade.stream_events(
        request_id=request_id,
        request=request,
        cursor=cursor,
    )


@router.get("/{request_id}/events/history")
async def list_run_event_history(
    request_id: str,
    from_seq: int | None = Query(default=None, ge=0),
    to_seq: int | None = Query(default=None, ge=0),
    from_ts: str | None = Query(default=None),
    to_ts: str | None = Query(default=None),
):
    return await run_read_facade.list_event_history(
        request_id=request_id,
        from_seq=from_seq,
        to_seq=to_seq,
        from_ts=from_ts,
        to_ts=to_ts,
    )


@router.get("/{request_id}/chat")
async def stream_run_chat(
    request_id: str,
    request: Request,
    cursor: int = Query(default=0, ge=0),
):
    return await run_read_facade.stream_chat(
        request_id=request_id,
        request=request,
        cursor=cursor,
    )


@router.get("/{request_id}/chat/history")
async def list_run_chat_history(
    request_id: str,
    from_seq: int | None = Query(default=None, ge=0),
    to_seq: int | None = Query(default=None, ge=0),
    from_ts: str | None = Query(default=None),
    to_ts: str | None = Query(default=None),
):
    return await run_read_facade.list_chat_history(
        request_id=request_id,
        from_seq=from_seq,
        to_seq=to_seq,
        from_ts=from_ts,
        to_ts=to_ts,
    )


@router.get("/{request_id}/logs/range")
async def get_run_log_range(
    request_id: str,
    stream: str = Query(...),
    byte_from: int = Query(default=0, ge=0),
    byte_to: int = Query(default=0, ge=0),
    attempt: int | None = Query(default=None, ge=1),
):
    return await run_read_facade.read_log_range(
        request_id=request_id,
        stream=stream,
        byte_from=byte_from,
        byte_to=byte_to,
        attempt=attempt,
    )


@router.get("/{request_id}/interaction/pending", response_model=InteractionPendingResponse)
async def get_interaction_pending(request_id: str):
    return await run_interaction_service.get_pending(
        request_id=request_id,
        run_store_backend=run_store,
    )


@router.post("/{request_id}/interaction/reply", response_model=InteractionReplyResponse)
async def reply_interaction(
    request_id: str,
    request: InteractionReplyRequest,
    background_tasks: BackgroundTasks,
):
    return await run_interaction_service.submit_reply(
        request_id=request_id,
        request=request,
        background_tasks=background_tasks,
        run_store_backend=run_store,
    )


@router.post("/{request_id}/interaction/auth/import", response_model=InteractionReplyResponse)
async def import_interaction_auth(
    request_id: str,
    background_tasks: BackgroundTasks,
    provider_id: str | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
):
    uploaded: dict[str, bytes] = {}
    for item in files:
        name = Path(item.filename or "").name.strip()
        if not name:
            continue
        uploaded[name] = await item.read()
    return await run_interaction_service.submit_auth_import(
        request_id=request_id,
        provider_id=provider_id,
        files=uploaded,
        background_tasks=background_tasks,
        run_store_backend=run_store,
    )


@router.get("/{request_id}/auth/session", response_model=AuthSessionStatusResponse)
async def get_auth_session_status(request_id: str):
    return await run_interaction_service.get_auth_session_status(
        request_id=request_id,
        run_store_backend=run_store,
    )

@router.post("/{request_id}/upload", response_model=RunUploadResponse)
async def upload_file(
    request_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(default=None),
    skill_package: UploadFile | None = File(default=None),
):
    request_record: dict[str, Any] | None = None
    source = "unknown"
    run_id_for_log: str | None = None
    try:
        with bind_request_logging_context(request_id=request_id, phase="upload"):
            log_event(
                logger,
                event="upload.request.received",
                phase="upload",
                outcome="start",
                request_id=request_id,
            )
            request_record = await run_store.get_request(request_id)
            if not request_record:
                raise ValueError(f"Request {request_id} not found")

            source = str(request_record.get("skill_source") or RequestSkillSource.INSTALLED.value)
            effective_runtime_options = request_record.get(
                "effective_runtime_options",
                request_record.get("runtime_options", {}),
            )
            runtime_options = request_record.get("runtime_options", {})
            skill = None
            skill_package_bytes: bytes | None = None
            temp_skill_package_hash = ""
            log_event(
                logger,
                event="upload.request.loaded",
                phase="upload",
                outcome="ok",
                request_id=request_id,
                engine=request_record.get("engine"),
                skill_source=source,
            )

            if source == RequestSkillSource.TEMP_UPLOAD.value:
                if skill_package is None:
                    raise HTTPException(status_code=422, detail="skill_package is required for temp_upload source")
                skill_package_bytes = await skill_package.read()
                temp_skill_package_hash = compute_bytes_hash(skill_package_bytes)
                from server.services.skill.temp_skill_run_manager import temp_skill_run_manager

                skill = await temp_skill_run_manager.inspect_skill_package(skill_package_bytes)
                await run_store.update_request_skill_identity(
                    request_id,
                    skill_id=skill.id,
                    temp_skill_manifest_id=skill.id,
                    temp_skill_manifest_json=skill.model_dump(mode="json"),
                    temp_skill_package_sha256=temp_skill_package_hash,
                )
                request_record = await run_store.get_request(request_id) or request_record
            else:
                skill = skill_registry.get_skill(request_record["skill_id"])
                if not skill:
                    raise ValueError(f"Skill '{request_record['skill_id']}' not found")
            log_event(
                logger,
                event="upload.payload.validated",
                phase="upload",
                outcome="ok",
                request_id=request_id,
                engine=request_record.get("engine"),
                skill_source=source,
                skill_id=skill.id if skill is not None else None,
            )
            stage_root = Path(config.SYSTEM.TMP_UPLOADS_DIR) / request_id
            uploads_dir = stage_root / "uploads"
            if stage_root.exists():
                shutil.rmtree(stage_root, ignore_errors=True)
            uploads_dir.mkdir(parents=True, exist_ok=True)
            try:
                log_event(
                    logger,
                    event="upload.temp_staged",
                    phase="upload",
                    outcome="ok",
                    request_id=request_id,
                    stage_dir=str(uploads_dir),
                )
                extracted_files: list[str] = []
                if file is not None:
                    content = await file.read()
                    extracted_files = _extract_zip_to_dir(content, uploads_dir)

                declared_file_path_errors = schema_validator.validate_declared_file_input_paths(
                    skill,
                    {"input": request_record.get("input", {})},
                    uploads_dir,
                )
                if declared_file_path_errors:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Input validation failed: {declared_file_path_errors}",
                    )

                manifest = build_input_manifest(uploads_dir)
                manifest_hash = compute_input_manifest_hash(manifest)
                log_event(
                    logger,
                    event="upload.manifest.built",
                    phase="upload",
                    outcome="ok",
                    request_id=request_id,
                    manifest_hash=manifest_hash,
                    extracted_files=len(extracted_files),
                )
                skill_fingerprint = compute_skill_fingerprint(skill, request_record["engine"])
                inline_input_hash = compute_inline_input_hash(request_record.get("input", {}))
                if source == RequestSkillSource.TEMP_UPLOAD.value:
                    inline_input_hash = compute_inline_input_hash({})

                await run_store.update_request_manifest(
                    request_id,
                    None,
                    manifest_hash,
                    request_upload_mode="uploaded",
                )
                log_event(
                    logger,
                    event="upload.request_state.persisted",
                    phase="upload",
                    outcome="ok",
                    request_id=request_id,
                    request_upload_mode="uploaded",
                    manifest_hash=manifest_hash,
                )
                cache_key = compute_cache_key(
                    skill_id=skill.id,
                    engine=request_record["engine"],
                    skill_fingerprint=skill_fingerprint,
                    parameter=request_record["parameter"],
                    engine_options=request_record["engine_options"],
                    input_manifest_hash=manifest_hash,
                    inline_input_hash=inline_input_hash,
                    temp_skill_package_hash=temp_skill_package_hash,
                )
                await run_store.update_request_cache_key(request_id, cache_key, skill_fingerprint)
                log_event(
                    logger,
                    event="upload.cache_key.computed",
                    phase="upload",
                    outcome="ok",
                    request_id=request_id,
                    cache_key=cache_key,
                    skill_fingerprint=skill_fingerprint,
                )
                cache_enabled = is_cache_enabled(effective_runtime_options)
                if cache_enabled:
                    cached_run = await run_store.get_cached_run_for_source(cache_key, source)
                    if cached_run:
                        await run_store.bind_request_run_id(
                            request_id,
                            cached_run,
                            status=RunStatus.SUCCEEDED.value,
                        )
                        log_event(
                            logger,
                            event="upload.cache.hit",
                            phase="upload",
                            outcome="ok",
                            request_id=request_id,
                            run_id=cached_run,
                            cache_key=cache_key,
                            skill_source=source,
                        )
                        return RunUploadResponse(
                            request_id=request_id,
                            cache_hit=True,
                            status=RunStatus.SUCCEEDED,
                            extracted_files=extracted_files,
                        )
                log_event(
                    logger,
                    event="upload.cache.miss",
                    phase="upload",
                    outcome="ok",
                    request_id=request_id,
                    cache_key=cache_key,
                    skill_source=source,
                )
                request_skill_source = (
                    RequestSkillSource.TEMP_UPLOAD
                    if source == RequestSkillSource.TEMP_UPLOAD.value
                    else RequestSkillSource.INSTALLED
                )
                run_status = workspace_manager.create_run_for_skill(
                    RunCreateRequest(
                        skill_source=request_skill_source,
                        skill_id=skill.id,
                        engine=request_record["engine"],
                        input=request_record.get("input", {}),
                        parameter=request_record["parameter"],
                        model=request_record["engine_options"].get("model"),
                        runtime_options=effective_runtime_options,
                    ),
                    skill=skill,
                )
                run_id_for_log = run_status.run_id
                log_event(
                    logger,
                    event="upload.run.created",
                    phase="upload",
                    outcome="ok",
                    request_id=request_id,
                    run_id=run_status.run_id,
                    engine=request_record["engine"],
                )
                run_dir = workspace_manager.get_run_dir(run_status.run_id)
                if run_dir is None:
                    raise HTTPException(status_code=500, detail="Run directory not found")
                _copy_tree(uploads_dir, run_dir / "uploads")
                run_cache_key: str | None = cache_key if cache_enabled else None
                await run_store.create_run(run_status.run_id, run_cache_key, RunStatus.QUEUED)
                await run_store.bind_request_run_id(
                    request_id,
                    run_status.run_id,
                    status=RunStatus.QUEUED.value,
                )
                log_event(
                    logger,
                    event="upload.request_run.bound",
                    phase="upload",
                    outcome="ok",
                    request_id=request_id,
                    run_id=run_status.run_id,
                )
            finally:
                shutil.rmtree(stage_root, ignore_errors=True)
            run_audit_contract_service.initialize_run_audit(run_dir=run_dir)
            effective_execution_mode_obj = effective_runtime_options.get(
                "execution_mode",
                runtime_options.get("execution_mode", ExecutionMode.AUTO.value),
            )
            execution_mode = (
                effective_execution_mode_obj
                if isinstance(effective_execution_mode_obj, str)
                else ExecutionMode.AUTO.value
            )
            with contextlib.ExitStack() as run_log_stack:
                run_log_stack.enter_context(
                    bind_run_logging_context(
                        run_id=run_status.run_id,
                        request_id=request_id,
                        attempt_number=None,
                        phase="dispatch",
                    )
                )
                run_log_stack.enter_context(
                    RunServiceLogMirrorSession.open_run_scope(
                        run_dir=run_dir,
                        run_id=run_status.run_id,
                    )
                )
                log_event(
                    logger,
                    event="upload.dispatch.started",
                    phase="dispatch",
                    outcome="start",
                    request_id=request_id,
                    run_id=run_status.run_id,
                    engine=request_record["engine"],
                )
                run_audit_contract_service.write_request_input_snapshot(
                    run_dir=run_dir,
                    request_payload=request_record,
                )
                if source == RequestSkillSource.TEMP_UPLOAD.value:
                    if skill_package_bytes is None:
                        raise HTTPException(status_code=500, detail="missing temp skill package payload")
                    run_folder_bootstrapper.materialize_temp_skill_package(
                        package_bytes=skill_package_bytes,
                        run_dir=run_dir,
                        engine_name=request_record["engine"],
                        execution_mode=execution_mode,
                        source=RunLocalSkillSource.TEMP_UPLOAD,
                    )
                else:
                    run_folder_bootstrapper.materialize_skill(
                        skill=skill,
                        run_dir=run_dir,
                        engine_name=request_record["engine"],
                        execution_mode=execution_mode,
                        source=RunLocalSkillSource.INSTALLED,
                    )
                await run_state_service.initialize_queued_state(
                    run_dir=run_dir,
                    request_id=request_id,
                    run_id=run_status.run_id,
                    request_record=request_record,
                    run_store_backend=run_store,
                )
                merged_options = {**request_record["engine_options"], **effective_runtime_options}
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
                log_event(
                    logger,
                    event="upload.dispatch.completed",
                    phase="dispatch",
                    outcome="ok",
                    request_id=request_id,
                    run_id=run_status.run_id,
                    engine=request_record["engine"],
                )
            background_tasks.add_task(
                job_orchestrator.run_job,
                run_id=run_status.run_id,
                skill_id=skill.id,
                engine_name=request_record["engine"],
                options=merged_options,
                cache_key=run_cache_key
            )
            return RunUploadResponse(
                request_id=request_id,
                cache_hit=False,
                status=run_status.status,
                extracted_files=extracted_files,
            )
    except ValueError as e:
        log_event(
            logger,
            event="upload.failed",
            phase="upload",
            outcome="error",
            level=logging.ERROR,
            request_id=request_id,
            run_id=run_id_for_log,
            error_code="VALUE_ERROR",
            error_type=type(e).__name__,
            detail=str(e),
            skill_source=source,
        )
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e:
        log_event(
            logger,
            event="upload.failed",
            phase="upload",
            outcome="error",
            level=logging.ERROR,
            request_id=request_id,
            run_id=run_id_for_log,
            error_code=f"HTTP_{e.status_code}",
            error_type="HTTPException",
            detail=e.detail,
            skill_source=source,
        )
        raise
    except Exception as e:
        # Router boundary mapping: preserve HTTP 500 contract for unclassified errors.
        logger.exception(
            "jobs.upload_file failed; returning HTTP 500",
            extra={
                "component": "router.jobs",
                "action": "upload_file",
                "error_type": type(e).__name__,
                "fallback": "http_500",
            },
        )
        log_event(
            logger,
            event="upload.failed",
            phase="upload",
            outcome="error",
            level=logging.ERROR,
            request_id=request_id,
            run_id=run_id_for_log,
            error_code="UNCLASSIFIED_EXCEPTION",
            error_type=type(e).__name__,
            detail=str(e),
            skill_source=source,
        )
        raise HTTPException(status_code=500, detail=str(e))


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


async def _read_pending_auth_session_id(request_id: str) -> str | None:
    pending = await maybe_await(run_store.get_pending_auth(request_id))
    if not isinstance(pending, dict):
        return None
    value = pending.get("auth_session_id")
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


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


@router.post("/cleanup", response_model=RunCleanupResponse)
async def cleanup_runs():
    try:
        counts = await run_cleanup_manager.clear_all()
        return RunCleanupResponse(
            runs_deleted=counts.get("runs", 0),
            requests_deleted=counts.get("requests", 0),
            cache_entries_deleted=counts.get("cache_entries", 0)
        )
    except Exception as e:
        # Router boundary mapping: preserve HTTP 500 contract for cleanup failures.
        logger.exception(
            "jobs.cleanup_runs failed; returning HTTP 500",
            extra={
                "component": "router.jobs",
                "action": "cleanup_runs",
                "error_type": type(e).__name__,
                "fallback": "http_500",
            },
        )
        raise HTTPException(status_code=500, detail=str(e))
