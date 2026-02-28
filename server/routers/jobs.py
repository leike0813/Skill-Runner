"""
API Router for Job Management.

Exposes endpoints for:
- Creating new jobs (POST /jobs)
- Querying job status (GET /jobs/{request_id})
- Uploading files to a job workspace (POST /jobs/{request_id}/upload)
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Query, Request  # type: ignore[import-not-found]
from typing import Any
from ..models import (
    CancelResponse,
    ExecutionMode,
    InteractionPendingResponse,
    InteractionReplyRequest,
    InteractionReplyResponse,
    RunCreateRequest,
    RunCreateResponse,
    RunUploadResponse,
    RequestStatusResponse,
    RecoveryState,
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
from ..services.orchestration.model_registry import model_registry
from ..services.platform.cache_key_builder import (
    compute_skill_fingerprint,
    compute_input_manifest_hash,
    compute_inline_input_hash,
    compute_cache_key,
)
from ..services.orchestration.run_store import run_store
from ..services.orchestration.run_cleanup_manager import run_cleanup_manager
from ..services.platform.concurrency_manager import concurrency_manager
from ..runtime.observability.run_observability import run_observability_service
from ..services.orchestration.engine_policy import resolve_skill_engine_policy
from ..services.orchestration.run_execution_core import (
    declared_execution_modes,
    ensure_skill_engine_supported,
    ensure_skill_execution_mode_supported,
    is_cache_enabled,
    validate_runtime_and_model_options,
)
from ..services.orchestration.run_interaction_service import run_interaction_service
from ..runtime.observability.run_read_facade import run_read_facade
from ..runtime.observability.run_source_adapter import RunSourceCapabilities
import uuid
import json

router = APIRouter(prefix="/jobs", tags=["jobs"])

install_runtime_protocol_ports()
install_runtime_observability_ports()


class _InstalledRouterSourceAdapter:
    source = "installed"
    cache_namespace = "cache_entries"
    capabilities = RunSourceCapabilities(
        supports_pending_reply=True,
        supports_event_history=True,
        supports_log_range=True,
        supports_inline_input_create=True,
    )

    def get_request(self, request_id: str):
        return run_store.get_request(request_id)

    def get_cached_run(self, cache_key: str):
        return run_store.get_cached_run(cache_key)

    def bind_cached_run(self, request_id: str, run_id: str) -> None:
        run_store.update_request_run_id(request_id, run_id)

    def mark_run_started(self, request_id: str, run_id: str) -> None:
        run_store.update_request_run_id(request_id, run_id)

    def mark_failed(self, request_id: str, error_message: str) -> None:
        _ = request_id
        _ = error_message

    def get_run_job_temp_request_id(self, request_id: str) -> str | None:
        _ = request_id
        return None

    def build_cancel_kwargs(self, request_id: str) -> dict[str, str]:
        return {"request_id": request_id}


installed_source_adapter = _InstalledRouterSourceAdapter()

@router.post("", response_model=RunCreateResponse)
async def create_run(request: RunCreateRequest, background_tasks: BackgroundTasks):
    # Verify skill exists
    skill = skill_registry.get_skill(request.skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{request.skill_id}' not found")

    try:
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
        execution_mode = runtime_opts.get("execution_mode", ExecutionMode.AUTO.value)
        ensure_skill_execution_mode_supported(
            skill_id=skill.id,
            requested_mode=execution_mode,
            declared_modes=declared_execution_modes(skill),
        )

        request_id = str(uuid.uuid4())
        inline_input = request.input if isinstance(request.input, dict) else {}
        inline_input_hash = compute_inline_input_hash(inline_input)
        inline_input_errors = schema_validator.validate_inline_input_create(skill, inline_input)
        if inline_input_errors:
            raise HTTPException(status_code=400, detail=f"Input validation failed: {inline_input_errors}")

        request_payload = request.model_dump()
        request_payload["engine_options"] = engine_opts
        request_payload["runtime_options"] = runtime_opts
        workspace_manager.create_request(request_id, request_payload)
        run_store.create_request(
            request_id=request_id,
            skill_id=request.skill_id,
            engine=request.engine,
            input_data=inline_input,
            parameter=request.parameter,
            engine_options=engine_opts,
            runtime_options=runtime_opts
        )

        has_input_schema = bool(skill.schemas and "input" in skill.schemas)
        has_required_file_inputs = schema_validator.has_required_file_inputs(skill)
        cache_enabled = is_cache_enabled(runtime_opts)
        if not has_input_schema or not has_required_file_inputs:
            manifest_path = workspace_manager.write_input_manifest(request_id)
            manifest_hash = compute_input_manifest_hash(json.loads(manifest_path.read_text()))
            skill_fingerprint = compute_skill_fingerprint(skill, request.engine)
            cache_key = compute_cache_key(
                skill_id=request.skill_id,
                engine=request.engine,
                skill_fingerprint=skill_fingerprint,
                parameter=request.parameter,
                engine_options=engine_opts,
                input_manifest_hash=manifest_hash,
                inline_input_hash=inline_input_hash
            )
            run_store.update_request_manifest(request_id, str(manifest_path), manifest_hash)
            run_store.update_request_cache_key(request_id, cache_key, skill_fingerprint)
            if cache_enabled:
                cached_run = installed_source_adapter.get_cached_run(cache_key)
                if cached_run:
                    installed_source_adapter.bind_cached_run(request_id, cached_run)
                    return RunCreateResponse(
                        request_id=request_id,
                        cache_hit=True,
                        status=RunStatus.SUCCEEDED
                    )

            run_request = RunCreateRequest(
                skill_id=request.skill_id,
                engine=request.engine,
                input=inline_input,
                parameter=request.parameter,
                model=request.model,
                runtime_options=runtime_opts
            )
            run_status = workspace_manager.create_run(run_request)
            run_cache_key: str | None = cache_key if cache_enabled else None
            run_store.create_run(run_status.run_id, run_cache_key, RunStatus.QUEUED)
            installed_source_adapter.mark_run_started(request_id, run_status.run_id)
            merged_options = {**engine_opts, **runtime_opts}
            admitted = await concurrency_manager.admit_or_reject()
            if not admitted:
                raise HTTPException(status_code=429, detail="Job queue is full")
            background_tasks.add_task(
                job_orchestrator.run_job,
                run_id=run_status.run_id,
                skill_id=request.skill_id,
                engine_name=request.engine,
                options=merged_options,
                cache_key=run_cache_key
            )
            return RunCreateResponse(
                request_id=request_id,
                cache_hit=False,
                status=run_status.status
            )

        return RunCreateResponse(
            request_id=request_id,
            cache_hit=False,
            status=None
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{request_id}", response_model=RequestStatusResponse)
async def get_run_status(request_id: str):
    request_record = run_store.get_request(request_id)
    if not request_record:
        raise HTTPException(status_code=404, detail="Request not found")
    run_id = request_record.get("run_id")
    if not run_id:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = workspace_manager.get_run_dir(run_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run not found")
    
    
    # Check for status.json created by JobOrchestrator
    status_file = run_dir / "status.json"
    
    current_status = RunStatus.QUEUED
    warnings = []
    error = None
    updated_at = None
    if status_file.exists():
        import json
        with open(status_file, 'r') as f:
            data = json.load(f)
            current_status = data.get("status", RunStatus.QUEUED)
            warnings = data.get("warnings", [])
            error = data.get("error")
            updated_at = data.get("updated_at")
            
    # Read run metadata
    skill_id = "unknown"
    engine = "unknown"
    input_file = run_dir / "input.json"
    if input_file.exists():
        import json
        with open(input_file, "r") as f:
            input_data = json.load(f)
        skill_id = input_data.get("skill_id", "unknown")
        engine = input_data.get("engine", "unknown")
    
    # Return status
    from datetime import datetime
    created_at = datetime.now()
    if input_file.exists():
        created_at = datetime.fromtimestamp(input_file.stat().st_mtime)
    if updated_at:
        try:
            updated_at_dt = datetime.fromisoformat(updated_at)
        except ValueError:
            updated_at_dt = datetime.now()
    else:
        updated_at_dt = datetime.now()
    auto_stats = run_store.get_auto_decision_stats(request_id)
    last_auto_decision_at_obj = auto_stats.get("last_auto_decision_at")
    last_auto_decision_at = None
    if isinstance(last_auto_decision_at_obj, str) and last_auto_decision_at_obj:
        try:
            last_auto_decision_at = datetime.fromisoformat(last_auto_decision_at_obj)
        except ValueError:
            last_auto_decision_at = None
    pending_interaction_id = (
        _read_pending_interaction_id(request_id)
        if current_status == RunStatus.WAITING_USER
        else None
    )
    runtime_options = request_record.get("runtime_options", {})
    interactive_auto_reply, interactive_reply_timeout_sec = _resolve_interactive_autoreply_runtime_options(runtime_options)
    interaction_count = run_store.get_interaction_count(request_id)
    recovery_info = run_store.get_recovery_info(run_id)
    recovered_at = None
    recovered_at_obj = recovery_info.get("recovered_at")
    if isinstance(recovered_at_obj, str) and recovered_at_obj:
        try:
            recovered_at = datetime.fromisoformat(recovered_at_obj)
        except ValueError:
            recovered_at = None

    return RequestStatusResponse(
        request_id=request_id,
        status=current_status, 
        skill_id=skill_id,
        engine=engine,
        created_at=created_at,
        updated_at=updated_at_dt,
        warnings=warnings,
        error=error,
        auto_decision_count=int(auto_stats.get("auto_decision_count") or 0),
        last_auto_decision_at=last_auto_decision_at,
        pending_interaction_id=pending_interaction_id,
        interaction_count=interaction_count,
        recovery_state=_parse_recovery_state(recovery_info.get("recovery_state")),
        recovered_at=recovered_at,
        recovery_reason=_coerce_str_or_none(recovery_info.get("recovery_reason")),
        interactive_auto_reply=interactive_auto_reply,
        interactive_reply_timeout_sec=interactive_reply_timeout_sec,
    )

@router.get("/{request_id}/result", response_model=RunResultResponse)
async def get_run_result(request_id: str):
    return run_read_facade.get_result(
        source_adapter=installed_source_adapter,
        request_id=request_id,
    )

@router.get("/{request_id}/artifacts", response_model=RunArtifactsResponse)
async def get_run_artifacts(request_id: str):
    return run_read_facade.get_artifacts(
        source_adapter=installed_source_adapter,
        request_id=request_id,
    )

@router.get("/{request_id}/bundle")
async def get_run_bundle(request_id: str):
    return run_read_facade.get_bundle(
        source_adapter=installed_source_adapter,
        request_id=request_id,
    )

@router.get("/{request_id}/artifacts/{artifact_path:path}")
async def download_run_artifact(request_id: str, artifact_path: str):
    return run_read_facade.get_artifact_file(
        source_adapter=installed_source_adapter,
        request_id=request_id,
        artifact_path=artifact_path,
    )

@router.get("/{request_id}/logs", response_model=RunLogsResponse)
async def get_run_logs(request_id: str):
    return run_read_facade.get_logs(
        source_adapter=installed_source_adapter,
        request_id=request_id,
    )


@router.post("/{request_id}/cancel", response_model=CancelResponse)
async def cancel_run(request_id: str):
    return await run_read_facade.cancel_run(
        source_adapter=installed_source_adapter,
        request_id=request_id,
    )


@router.get("/{request_id}/events")
async def stream_run_events(
    request_id: str,
    request: Request,
    cursor: int = Query(default=0, ge=0),
):
    return await run_read_facade.stream_events(
        source_adapter=installed_source_adapter,
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
    return run_read_facade.list_event_history(
        source_adapter=installed_source_adapter,
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
    return run_read_facade.read_log_range(
        source_adapter=installed_source_adapter,
        request_id=request_id,
        stream=stream,
        byte_from=byte_from,
        byte_to=byte_to,
        attempt=attempt,
    )


@router.get("/{request_id}/interaction/pending", response_model=InteractionPendingResponse)
async def get_interaction_pending(request_id: str):
    return await run_interaction_service.get_pending(
        source_adapter=installed_source_adapter,
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
        source_adapter=installed_source_adapter,
        request_id=request_id,
        request=request,
        background_tasks=background_tasks,
        run_store_backend=run_store,
    )

@router.post("/{request_id}/upload", response_model=RunUploadResponse)
async def upload_file(request_id: str, file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    try:
        content = await file.read()
        result = workspace_manager.handle_upload(request_id, content)
        request_record = run_store.get_request(request_id)
        if not request_record:
            raise ValueError(f"Request {request_id} not found")

        skill = skill_registry.get_skill(request_record["skill_id"])
        if not skill:
            raise ValueError(f"Skill '{request_record['skill_id']}' not found")

        manifest_path = workspace_manager.write_input_manifest(request_id)
        manifest_hash = compute_input_manifest_hash(json.loads(manifest_path.read_text()))
        skill_fingerprint = compute_skill_fingerprint(skill, request_record["engine"])
        cache_key = compute_cache_key(
            skill_id=request_record["skill_id"],
            engine=request_record["engine"],
            skill_fingerprint=skill_fingerprint,
            parameter=request_record["parameter"],
            engine_options=request_record["engine_options"],
            input_manifest_hash=manifest_hash,
            inline_input_hash=compute_inline_input_hash(request_record.get("input", {}))
        )
        run_store.update_request_manifest(request_id, str(manifest_path), manifest_hash)
        run_store.update_request_cache_key(request_id, cache_key, skill_fingerprint)
        runtime_options = request_record.get("runtime_options", {})
        cache_enabled = is_cache_enabled(runtime_options)
        if cache_enabled:
            cached_run = installed_source_adapter.get_cached_run(cache_key)
            if cached_run:
                installed_source_adapter.bind_cached_run(request_id, cached_run)
                return RunUploadResponse(
                    request_id=request_id,
                    cache_hit=True,
                    extracted_files=result["extracted_files"]
                )

        run_status = workspace_manager.create_run(
            RunCreateRequest(
                skill_id=request_record["skill_id"],
                engine=request_record["engine"],
                input=request_record.get("input", {}),
                parameter=request_record["parameter"],
                model=request_record["engine_options"].get("model"),
                runtime_options=request_record["runtime_options"]
            )
        )
        workspace_manager.promote_request_uploads(request_id, run_status.run_id)
        run_cache_key: str | None = cache_key if cache_enabled else None
        run_store.create_run(run_status.run_id, run_cache_key, RunStatus.QUEUED)
        installed_source_adapter.mark_run_started(request_id, run_status.run_id)
        merged_options = {**request_record["engine_options"], **request_record["runtime_options"]}
        admitted = await concurrency_manager.admit_or_reject()
        if not admitted:
            raise HTTPException(status_code=429, detail="Job queue is full")
        background_tasks.add_task(
            job_orchestrator.run_job,
            run_id=run_status.run_id,
            skill_id=request_record["skill_id"],
            engine_name=request_record["engine"],
            options=merged_options,
            cache_key=run_cache_key
        )
        return RunUploadResponse(
            request_id=request_id,
            cache_hit=False,
            extracted_files=result["extracted_files"]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _read_pending_interaction_id(request_id: str) -> int | None:
    pending = run_store.get_pending_interaction(request_id)
    if not isinstance(pending, dict):
        return None
    value = pending.get("interaction_id")
    if value is None:
        return None
    try:
        interaction_id = int(value)
    except Exception:
        return None
    if interaction_id <= 0:
        return None
    return interaction_id


def _coerce_str_or_none(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        value = raw.strip()
        return value or None
    return str(raw)


def _resolve_interactive_autoreply_runtime_options(runtime_options: Any) -> tuple[bool | None, int | None]:
    if not isinstance(runtime_options, dict):
        return (None, None)
    auto_reply_obj = runtime_options.get("interactive_auto_reply")
    if not isinstance(auto_reply_obj, bool):
        return (None, None)
    timeout_obj = runtime_options.get("interactive_reply_timeout_sec")
    timeout_sec: int | None = None
    if isinstance(timeout_obj, int) and timeout_obj > 0:
        timeout_sec = timeout_obj
    return (auto_reply_obj, timeout_sec)


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
        counts = run_cleanup_manager.clear_all()
        return RunCleanupResponse(
            runs_deleted=counts.get("runs", 0),
            requests_deleted=counts.get("requests", 0),
            cache_entries_deleted=counts.get("cache_entries", 0)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
