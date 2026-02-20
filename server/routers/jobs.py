"""
API Router for Job Management.

Exposes endpoints for:
- Creating new jobs (POST /jobs)
- Querying job status (GET /jobs/{request_id})
- Uploading files to a job workspace (POST /jobs/{request_id}/upload)
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Query, Request  # type: ignore[import-not-found]
from fastapi.responses import FileResponse, StreamingResponse  # type: ignore[import-not-found]
from typing import Any
from ..models import (
    CancelResponse,
    ExecutionMode,
    InteractiveErrorCode,
    InteractionPendingResponse,
    InteractionReplyRequest,
    InteractionReplyResponse,
    PendingInteraction,
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
from ..services.workspace_manager import workspace_manager
from ..services.skill_registry import skill_registry
from ..services.job_orchestrator import job_orchestrator
from ..services.schema_validator import schema_validator
from ..services.options_policy import options_policy
from ..services.model_registry import model_registry
from ..services.cache_key_builder import (
    compute_skill_fingerprint,
    compute_input_manifest_hash,
    compute_inline_input_hash,
    compute_cache_key,
)
from ..services.run_store import run_store
from ..services.run_cleanup_manager import run_cleanup_manager
from ..services.concurrency_manager import concurrency_manager
from ..services.run_observability import run_observability_service
from ..services.engine_policy import SkillEnginePolicy, resolve_skill_engine_policy
import uuid
import json
from pathlib import Path

router = APIRouter(prefix="/jobs", tags=["jobs"])

TERMINAL_STATUSES = {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED}
ACTIVE_CANCELABLE_STATUSES = {RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.WAITING_USER}

@router.post("", response_model=RunCreateResponse)
async def create_run(request: RunCreateRequest, background_tasks: BackgroundTasks):
    # Verify skill exists
    skill = skill_registry.get_skill(request.skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{request.skill_id}' not found")

    try:
        engine_policy = resolve_skill_engine_policy(skill)
        _ensure_skill_engine_supported(
            skill_id=skill.id,
            requested_engine=request.engine,
            policy=engine_policy,
        )
        runtime_opts = options_policy.validate_runtime_options(request.runtime_options)
        execution_mode = runtime_opts.get("execution_mode", ExecutionMode.AUTO.value)
        is_interactive = execution_mode == ExecutionMode.INTERACTIVE.value
        _ensure_skill_execution_mode_supported(
            skill_id=skill.id,
            requested_mode=execution_mode,
            declared_modes=_declared_execution_modes(skill),
        )
        engine_opts: dict[str, Any] = {}
        if request.model:
            validated = model_registry.validate_model(request.engine, request.model)
            engine_opts["model"] = validated["model"]
            if "model_reasoning_effort" in validated:
                engine_opts["model_reasoning_effort"] = validated["model_reasoning_effort"]

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
        no_cache = bool(runtime_opts.get("no_cache"))
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
            if not no_cache and not is_interactive:
                cached_run = run_store.get_cached_run(cache_key)
                if cached_run:
                    run_store.update_request_run_id(request_id, cached_run)
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
            run_cache_key: str | None = None if is_interactive else cache_key
            run_store.create_run(run_status.run_id, run_cache_key, RunStatus.QUEUED)
            run_store.update_request_run_id(request_id, run_status.run_id)
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
    )

@router.get("/{request_id}/result", response_model=RunResultResponse)
async def get_run_result(request_id: str):
    request_record = run_store.get_request(request_id)
    if not request_record:
        raise HTTPException(status_code=404, detail="Request not found")
    run_id = request_record.get("run_id")
    if not run_id:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = workspace_manager.get_run_dir(run_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run not found")

    result_path = run_dir / "result" / "result.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Run result not found")

    with open(result_path, "r") as f:
        result_payload = json.load(f)

    return RunResultResponse(request_id=request_id, result=result_payload)

@router.get("/{request_id}/artifacts", response_model=RunArtifactsResponse)
async def get_run_artifacts(request_id: str):
    request_record = run_store.get_request(request_id)
    if not request_record:
        raise HTTPException(status_code=404, detail="Request not found")
    run_id = request_record.get("run_id")
    if not run_id:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = workspace_manager.get_run_dir(run_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run not found")

    artifacts_dir = run_dir / "artifacts"
    artifacts = []
    if artifacts_dir.exists():
        for path in artifacts_dir.rglob("*"):
            if path.is_file():
                artifacts.append(path.relative_to(run_dir).as_posix())

    return RunArtifactsResponse(request_id=request_id, artifacts=artifacts)

@router.get("/{request_id}/bundle")
async def get_run_bundle(request_id: str):
    request_record = run_store.get_request(request_id)
    if not request_record:
        raise HTTPException(status_code=404, detail="Request not found")
    run_id = request_record.get("run_id")
    if not run_id:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = workspace_manager.get_run_dir(run_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run not found")

    debug_mode = bool(request_record.get("runtime_options", {}).get("debug"))
    bundle_name = "run_bundle_debug.zip" if debug_mode else "run_bundle.zip"
    bundle_path = run_dir / "bundle" / bundle_name
    if not bundle_path.exists():
        from ..services.job_orchestrator import job_orchestrator
        job_orchestrator._build_run_bundle(run_dir, debug_mode)

    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="Bundle not found")

    return FileResponse(path=bundle_path, filename=bundle_path.name)

@router.get("/{request_id}/artifacts/{artifact_path:path}")
async def download_run_artifact(request_id: str, artifact_path: str):
    request_record = run_store.get_request(request_id)
    if not request_record:
        raise HTTPException(status_code=404, detail="Request not found")
    run_id = request_record.get("run_id")
    if not run_id:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = workspace_manager.get_run_dir(run_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run not found")
    if not artifact_path:
        raise HTTPException(status_code=400, detail="Artifact path is required")

    debug_mode = bool(request_record.get("runtime_options", {}).get("debug"))
    if not artifact_path.startswith("artifacts/"):
        raise HTTPException(status_code=404, detail="Artifact not found")

    target = (run_dir / artifact_path).resolve()
    run_root = run_dir.resolve()
    artifacts_root = (run_dir / "artifacts").resolve()
    if not str(target).startswith(str(artifacts_root)):
        raise HTTPException(status_code=400, detail="Invalid artifact path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")

    return FileResponse(path=target, filename=target.name)

@router.get("/{request_id}/logs", response_model=RunLogsResponse)
async def get_run_logs(request_id: str):
    request_record = run_store.get_request(request_id)
    if not request_record:
        raise HTTPException(status_code=404, detail="Request not found")
    run_id = request_record.get("run_id")
    if not run_id:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = workspace_manager.get_run_dir(run_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run not found")

    logs_dir = run_dir / "logs"
    if not logs_dir.exists():
        return RunLogsResponse(request_id=request_id)

    def _read_log(path: Path) -> str | None:
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    return RunLogsResponse(
        request_id=request_id,
        prompt=_read_log(logs_dir / "prompt.txt"),
        stdout=_read_log(logs_dir / "stdout.txt"),
        stderr=_read_log(logs_dir / "stderr.txt")
    )


@router.post("/{request_id}/cancel", response_model=CancelResponse)
async def cancel_run(request_id: str):
    request_record, run_dir = _get_request_and_run_dir(request_id)
    run_id_obj = request_record.get("run_id")
    if not isinstance(run_id_obj, str) or not run_id_obj:
        raise HTTPException(status_code=404, detail="Run not found")
    run_id = run_id_obj

    status, warnings, error, _updated_at = _read_run_status(run_dir)
    if status in TERMINAL_STATUSES:
        return CancelResponse(
            request_id=request_id,
            run_id=run_id,
            status=status,
            accepted=False,
            message="Run already in terminal state",
        )
    if status not in ACTIVE_CANCELABLE_STATUSES:
        return CancelResponse(
            request_id=request_id,
            run_id=run_id,
            status=status,
            accepted=False,
            message="Run is not cancelable",
        )

    accepted = await job_orchestrator.cancel_run(
        run_id=run_id,
        engine_name=str(request_record.get("engine", "")),
        run_dir=run_dir,
        status=status,
        request_id=request_id,
    )
    return CancelResponse(
        request_id=request_id,
        run_id=run_id,
        status=RunStatus.CANCELED,
        accepted=accepted,
        message="Cancel request accepted" if accepted else "Cancel already requested",
    )


@router.get("/{request_id}/events")
async def stream_run_events(
    request_id: str,
    request: Request,
    stdout_from: int = Query(default=0, ge=0),
    stderr_from: int = Query(default=0, ge=0),
):
    _request_record, run_dir = _get_request_and_run_dir(request_id)

    async def _event_stream():
        async for item in run_observability_service.iter_sse_events(
            run_dir=run_dir,
            request_id=request_id,
            stdout_from=stdout_from,
            stderr_from=stderr_from,
            is_disconnected=request.is_disconnected,
        ):
            yield run_observability_service.format_sse_frame(
                item["event"],
                item["data"],
            )

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{request_id}/interaction/pending", response_model=InteractionPendingResponse)
async def get_interaction_pending(request_id: str):
    request_record, run_dir = _get_request_and_run_dir(request_id)
    _ensure_interactive_mode(request_record)
    status, _, _, _ = _read_run_status(run_dir)
    pending_payload = run_store.get_pending_interaction(request_id)
    pending = None
    if pending_payload and status == RunStatus.WAITING_USER:
        pending = PendingInteraction.model_validate(pending_payload)
    return InteractionPendingResponse(
        request_id=request_id,
        status=status,
        pending=pending,
    )


@router.post("/{request_id}/interaction/reply", response_model=InteractionReplyResponse)
async def reply_interaction(
    request_id: str,
    request: InteractionReplyRequest,
    background_tasks: BackgroundTasks,
):
    request_record, run_dir = _get_request_and_run_dir(request_id)
    _ensure_interactive_mode(request_record)
    status, warnings, _, _ = _read_run_status(run_dir)
    if status != RunStatus.WAITING_USER:
        replay = _resolve_idempotent_replay(request_id, request, status)
        if replay:
            return replay
        raise HTTPException(status_code=409, detail="Run is not waiting for user interaction")

    pending_payload = run_store.get_pending_interaction(request_id)
    if not pending_payload:
        replay = _resolve_idempotent_replay(request_id, request, status)
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

    reply_state = run_store.submit_interaction_reply(
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

    profile = run_store.get_interactive_profile(request_id) or {}
    if profile.get("kind") == "sticky_process":
        sticky_runtime = run_store.get_sticky_wait_runtime(request_id)
        if not sticky_runtime:
            await _mark_run_failed(
                request_record=request_record,
                run_dir=run_dir,
                code=InteractiveErrorCode.INTERACTION_PROCESS_LOST.value,
                message="Sticky process runtime missing",
            )
            raise HTTPException(status_code=409, detail="sticky process lost")
        deadline_raw = sticky_runtime.get("wait_deadline_at")
        process_binding = sticky_runtime.get("process_binding") or {}
        if not deadline_raw:
            await _mark_run_failed(
                request_record=request_record,
                run_dir=run_dir,
                code=InteractiveErrorCode.INTERACTION_PROCESS_LOST.value,
                message="Sticky process deadline missing",
            )
            raise HTTPException(status_code=409, detail="sticky process lost")
        try:
            deadline = datetime.fromisoformat(str(deadline_raw))
        except ValueError:
            await _mark_run_failed(
                request_record=request_record,
                run_dir=run_dir,
                code=InteractiveErrorCode.INTERACTION_PROCESS_LOST.value,
                message="Sticky process deadline invalid",
            )
            raise HTTPException(status_code=409, detail="sticky process lost")
        if datetime.utcnow() > deadline:
            await _mark_run_failed(
                request_record=request_record,
                run_dir=run_dir,
                code=InteractiveErrorCode.INTERACTION_WAIT_TIMEOUT.value,
                message="Sticky process wait timeout",
            )
            raise HTTPException(status_code=409, detail="interaction wait timeout")
        if process_binding.get("alive") is False:
            await _mark_run_failed(
                request_record=request_record,
                run_dir=run_dir,
                code=InteractiveErrorCode.INTERACTION_PROCESS_LOST.value,
                message="Sticky process exited",
            )
            raise HTTPException(status_code=409, detail="sticky process lost")

    is_sticky_profile = profile.get("kind") == "sticky_process"
    next_status = RunStatus.RUNNING if is_sticky_profile else RunStatus.QUEUED
    _write_run_status(run_dir, next_status, warnings=warnings)
    run_id = request_record.get("run_id")
    if run_id:
        run_store.update_run_status(run_id, next_status)
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
        background_tasks.add_task(
            job_orchestrator.run_job,
            run_id=run_id,
            skill_id=request_record["skill_id"],
            engine_name=request_record["engine"],
            options=merged_options,
            cache_key=None,
        )
    return InteractionReplyResponse(
        request_id=request_id,
        status=next_status,
        accepted=True,
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
        no_cache = bool(request_record.get("runtime_options", {}).get("no_cache"))
        execution_mode = request_record.get("runtime_options", {}).get(
            "execution_mode", ExecutionMode.AUTO.value
        )
        is_interactive = execution_mode == ExecutionMode.INTERACTIVE.value
        if not no_cache and not is_interactive:
            cached_run = run_store.get_cached_run(cache_key)
            if cached_run:
                run_store.update_request_run_id(request_id, cached_run)
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
        run_cache_key: str | None = None if is_interactive else cache_key
        run_store.create_run(run_status.run_id, run_cache_key, RunStatus.QUEUED)
        run_store.update_request_run_id(request_id, run_status.run_id)
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


def _get_request_and_run_dir(request_id: str) -> tuple[dict[str, Any], Path]:
    request_record = run_store.get_request(request_id)
    if not request_record:
        raise HTTPException(status_code=404, detail="Request not found")
    run_id = request_record.get("run_id")
    if not run_id:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = workspace_manager.get_run_dir(run_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run not found")
    return request_record, run_dir


def _declared_execution_modes(skill: Any) -> set[str]:
    raw_modes = getattr(skill, "execution_modes", [ExecutionMode.AUTO.value]) or [
        ExecutionMode.AUTO.value
    ]
    modes: set[str] = set()
    for mode in raw_modes:
        if isinstance(mode, ExecutionMode):
            modes.add(mode.value)
        else:
            modes.add(str(mode))
    return modes


def _ensure_skill_execution_mode_supported(
    skill_id: str,
    requested_mode: str,
    declared_modes: set[str],
) -> None:
    if requested_mode in declared_modes:
        return
    raise HTTPException(
        status_code=400,
        detail={
            "code": "SKILL_EXECUTION_MODE_UNSUPPORTED",
            "message": (
                f"Skill '{skill_id}' does not support execution_mode "
                f"'{requested_mode}'"
            ),
            "declared_execution_modes": sorted(declared_modes),
            "requested_execution_mode": requested_mode,
        },
    )


def _ensure_skill_engine_supported(
    skill_id: str,
    requested_engine: str,
    policy: SkillEnginePolicy,
) -> None:
    if requested_engine in policy.effective_engines:
        return
    raise HTTPException(
        status_code=400,
        detail={
            "code": "SKILL_ENGINE_UNSUPPORTED",
            "message": f"Skill '{skill_id}' does not support engine '{requested_engine}'",
            "declared_engines": policy.declared_engines,
            "unsupport_engine": policy.unsupport_engine,
            "effective_engines": policy.effective_engines,
            "requested_engine": requested_engine,
        },
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


def _parse_recovery_state(raw: Any) -> RecoveryState:
    if isinstance(raw, RecoveryState):
        return raw
    if isinstance(raw, str):
        try:
            return RecoveryState(raw)
        except ValueError:
            return RecoveryState.NONE
    return RecoveryState.NONE


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
    request_record: dict[str, Any],
    run_dir: Path,
    code: str,
    message: str,
) -> None:
    error_payload = {"code": code, "message": message}
    _write_run_status(
        run_dir,
        RunStatus.FAILED,
        error=error_payload,
        effective_session_timeout_sec=run_store.get_effective_session_timeout(
            request_record.get("request_id", "")
        )
        if isinstance(request_record.get("request_id"), str)
        else None,
    )
    run_id = request_record.get("run_id")
    if run_id:
        run_store.update_run_status(run_id, RunStatus.FAILED)
        await concurrency_manager.release_slot()


def _resolve_idempotent_replay(
    request_id: str,
    request: InteractionReplyRequest,
    status: RunStatus,
) -> InteractionReplyResponse | None:
    if not request.idempotency_key:
        return None
    existing_reply = run_store.get_interaction_reply(
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
