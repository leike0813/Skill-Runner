import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, Request, UploadFile  # type: ignore[import-not-found]

from ..models import (
    CancelResponse,
    ExecutionMode,
    InteractionPendingResponse,
    InteractionReplyRequest,
    InteractionReplyResponse,
    RecoveryState,
    RequestStatusResponse,
    RunArtifactsResponse,
    RunCreateRequest,
    RunLogsResponse,
    RunResultResponse,
    RunStatus,
    TempSkillRunCreateRequest,
    TempSkillRunCreateResponse,
    TempSkillRunUploadResponse,
)
from ..services.concurrency_manager import concurrency_manager
from ..services.job_orchestrator import job_orchestrator
from ..services.model_registry import model_registry
from ..services.cache_key_builder import (
    compute_bytes_hash,
    compute_cache_key,
    compute_inline_input_hash,
    compute_input_manifest_hash,
    compute_skill_fingerprint,
)
from ..services.run_store import run_store
from ..services.temp_skill_run_manager import temp_skill_run_manager
from ..services.temp_skill_run_store import temp_skill_run_store
from ..services.workspace_manager import workspace_manager
from ..services.engine_policy import resolve_skill_engine_policy
from ..services.run_execution_core import (
    declared_execution_modes,
    ensure_skill_engine_supported,
    ensure_skill_execution_mode_supported,
    is_cache_enabled,
    validate_runtime_and_model_options,
)
from ..services.run_interaction_service import run_interaction_service
from ..services.run_read_facade import run_read_facade
from ..services.run_source_adapter import RunSourceCapabilities


router = APIRouter(prefix="/temp-skill-runs", tags=["temp-skill-runs"])


class _TempRouterSourceAdapter:
    source = "temp"
    cache_namespace = "temp_cache_entries"
    capabilities = RunSourceCapabilities(
        supports_pending_reply=True,
        supports_event_history=True,
        supports_log_range=True,
        supports_inline_input_create=False,
    )

    def get_request(self, request_id: str):
        return temp_skill_run_store.get_request(request_id)

    def get_cached_run(self, cache_key: str):
        return run_store.get_temp_cached_run(cache_key)

    def bind_cached_run(self, request_id: str, run_id: str) -> None:
        temp_skill_run_store.bind_cached_run(request_id, run_id)
        if run_store.get_request(request_id):
            run_store.update_request_run_id(request_id, run_id)

    def mark_run_started(self, request_id: str, run_id: str) -> None:
        temp_skill_run_store.update_run_started(request_id, run_id)
        if run_store.get_request(request_id):
            run_store.update_request_run_id(request_id, run_id)

    def mark_failed(self, request_id: str, error_message: str) -> None:
        temp_skill_run_store.update_status(
            request_id=request_id,
            status=RunStatus.FAILED,
            error=error_message,
        )

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

        request_id = str(uuid.uuid4())
        request_payload = {
            "skill_id": "__temporary__",
            "engine": request.engine,
            "parameter": request.parameter,
            "model": request.model,
            "engine_options": engine_opts,
            "runtime_options": runtime_opts,
        }
        workspace_manager.create_request(request_id, request_payload)
        temp_skill_run_manager.create_request_dirs(request_id)
        temp_skill_run_store.create_request(
            request_id=request_id,
            engine=request.engine,
            parameter=request.parameter,
            model=request.model,
            engine_options=engine_opts,
            runtime_options=runtime_opts,
        )
        return TempSkillRunCreateResponse(request_id=request_id, status=RunStatus.QUEUED)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{request_id}/upload", response_model=TempSkillRunUploadResponse)
async def upload_temp_skill_and_start(
    request_id: str,
    background_tasks: BackgroundTasks,
    skill_package: UploadFile = File(...),
    file: UploadFile | None = File(default=None),
):
    record = temp_skill_run_store.get_request(request_id)
    if not record:
        raise HTTPException(status_code=404, detail="Request not found")
    if record.get("run_id"):
        raise HTTPException(status_code=400, detail="Run already started")

    run_status = None
    extracted_files: list[str] = []
    try:
        skill_bytes = await skill_package.read()
        skill_package_hash = compute_bytes_hash(skill_bytes)
        skill = temp_skill_run_manager.stage_skill_package(request_id, skill_bytes)
        engine_policy = resolve_skill_engine_policy(skill)
        ensure_skill_engine_supported(
            skill_id=skill.id,
            requested_engine=record["engine"],
            policy=engine_policy,
        )
        requested_mode = record.get("runtime_options", {}).get(
            "execution_mode", ExecutionMode.AUTO.value
        )
        ensure_skill_execution_mode_supported(
            skill_id=skill.id,
            requested_mode=requested_mode,
            declared_modes=declared_execution_modes(skill),
        )

        if file is not None:
            input_bytes = await file.read()
            upload_res = workspace_manager.handle_upload(request_id, input_bytes)
            extracted_files = upload_res.get("extracted_files", [])

        runtime_options = record.get("runtime_options", {})
        cache_enabled = is_cache_enabled(runtime_options)
        _ensure_temp_request_synced_in_run_store(
            request_id=request_id,
            temp_record=record,
            skill_id=skill.id,
        )
        manifest_path = workspace_manager.write_input_manifest(request_id)
        manifest_hash = compute_input_manifest_hash(
            json.loads(manifest_path.read_text(encoding="utf-8"))
        )
        run_store.update_request_manifest(request_id, str(manifest_path), manifest_hash)
        skill_fingerprint = compute_skill_fingerprint(skill, record["engine"])
        cache_key = compute_cache_key(
            skill_id=skill.id,
            engine=record["engine"],
            skill_fingerprint=skill_fingerprint,
            parameter=record["parameter"],
            engine_options=record["engine_options"],
            input_manifest_hash=manifest_hash,
            inline_input_hash=compute_inline_input_hash({}),
            temp_skill_package_hash=skill_package_hash,
        )
        run_store.update_request_cache_key(request_id, cache_key, skill_fingerprint)
        if cache_enabled:
            cached_run = temp_source_adapter.get_cached_run(cache_key)
            if cached_run:
                temp_source_adapter.bind_cached_run(request_id, cached_run)
                temp_skill_run_manager.on_terminal(
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
            skill_id=skill.id,
            engine=record["engine"],
            parameter=record["parameter"],
            model=record.get("model"),
            runtime_options=record["runtime_options"],
        )
        run_status = workspace_manager.create_run_for_skill(run_request, skill)
        workspace_manager.promote_request_uploads(request_id, run_status.run_id)
        run_cache_key: str | None = cache_key if cache_enabled else None
        run_store.create_run(run_status.run_id, run_cache_key, RunStatus.QUEUED)
        temp_source_adapter.mark_run_started(request_id, run_status.run_id)

        merged_options = {**record["engine_options"], **record["runtime_options"]}
        admitted = await concurrency_manager.admit_or_reject()
        if not admitted:
            raise HTTPException(status_code=429, detail="Job queue is full")
        background_tasks.add_task(
            job_orchestrator.run_job,
            run_id=run_status.run_id,
            skill_id=skill.id,
            engine_name=record["engine"],
            options=merged_options,
            cache_key=run_cache_key,
            skill_override=skill,
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
            temp_skill_run_store.update_status(request_id, RunStatus.FAILED, error=error_message)
        elif record.get("run_id") is None:
            temp_skill_run_store.update_status(request_id, RunStatus.FAILED, error=error_message)
        raise
    except ValueError as exc:
        temp_skill_run_store.update_status(request_id, RunStatus.FAILED, error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        temp_skill_run_store.update_status(request_id, RunStatus.FAILED, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{request_id}", response_model=RequestStatusResponse)
async def get_temp_skill_run_status(request_id: str):
    rec = temp_skill_run_store.get_request(request_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Request not found")

    created_at = _parse_dt(rec.get("created_at"))
    updated_at = _parse_dt(rec.get("updated_at"))
    run_id = rec.get("run_id")

    if not run_id:
        auto_stats = run_store.get_auto_decision_stats(request_id)
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
            interaction_count=run_store.get_interaction_count(request_id),
            recovery_state=RecoveryState.NONE,
            recovered_at=None,
            recovery_reason=None,
        )

    run_dir = workspace_manager.get_run_dir(run_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run not found")

    status_file = run_dir / "status.json"
    status = RunStatus(rec.get("status", RunStatus.QUEUED.value))
    warnings: list[Any] = []
    error = {"message": rec["error"]} if rec.get("error") else None
    if status_file.exists():
        payload = json.loads(status_file.read_text(encoding="utf-8"))
        status = RunStatus(payload.get("status", RunStatus.QUEUED.value))
        warnings = payload.get("warnings", [])
        error = payload.get("error")
        updated_at = _parse_dt(payload.get("updated_at"))
    recovery_info = run_store.get_recovery_info(run_id)
    recovered_at_raw = recovery_info.get("recovered_at")
    recovered_at = _parse_dt(recovered_at_raw) if recovered_at_raw else None
    auto_stats = run_store.get_auto_decision_stats(request_id)
    pending_interaction_id = (
        _read_pending_interaction_id(request_id)
        if status == RunStatus.WAITING_USER
        else None
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
        interaction_count=run_store.get_interaction_count(request_id),
        recovery_state=_parse_recovery_state(recovery_info.get("recovery_state")),
        recovered_at=recovered_at,
        recovery_reason=_coerce_str_or_none(recovery_info.get("recovery_reason")),
    )


@router.get("/{request_id}/result", response_model=RunResultResponse)
async def get_temp_skill_run_result(request_id: str):
    return run_read_facade.get_result(
        source_adapter=temp_source_adapter,
        request_id=request_id,
    )


@router.get("/{request_id}/artifacts", response_model=RunArtifactsResponse)
async def get_temp_skill_run_artifacts(request_id: str):
    return run_read_facade.get_artifacts(
        source_adapter=temp_source_adapter,
        request_id=request_id,
    )


@router.get("/{request_id}/bundle")
async def get_temp_skill_run_bundle(request_id: str):
    return run_read_facade.get_bundle(
        source_adapter=temp_source_adapter,
        request_id=request_id,
    )


@router.get("/{request_id}/artifacts/{artifact_path:path}")
async def download_temp_skill_artifact(request_id: str, artifact_path: str):
    return run_read_facade.get_artifact_file(
        source_adapter=temp_source_adapter,
        request_id=request_id,
        artifact_path=artifact_path,
    )


@router.get("/{request_id}/logs", response_model=RunLogsResponse)
async def get_temp_skill_run_logs(request_id: str):
    return run_read_facade.get_logs(
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
    stdout_from: int = Query(default=0, ge=0),
    stderr_from: int = Query(default=0, ge=0),
):
    return await run_read_facade.stream_events(
        source_adapter=temp_source_adapter,
        request_id=request_id,
        request=request,
        cursor=cursor,
        stdout_from=stdout_from,
        stderr_from=stderr_from,
    )


@router.get("/{request_id}/events/history")
async def list_temp_skill_run_event_history(
    request_id: str,
    from_seq: int | None = Query(default=None, ge=0),
    to_seq: int | None = Query(default=None, ge=0),
    from_ts: str | None = Query(default=None),
    to_ts: str | None = Query(default=None),
):
    return run_read_facade.list_event_history(
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
):
    return run_read_facade.read_log_range(
        source_adapter=temp_source_adapter,
        request_id=request_id,
        stream=stream,
        byte_from=byte_from,
        byte_to=byte_to,
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


def _ensure_temp_request_synced_in_run_store(
    *,
    request_id: str,
    temp_record: dict[str, Any],
    skill_id: str,
) -> None:
    if run_store.get_request(request_id):
        return
    run_store.create_request(
        request_id=request_id,
        skill_id=skill_id,
        engine=str(temp_record.get("engine", "")),
        input_data={},
        parameter=temp_record.get("parameter", {}),
        engine_options=temp_record.get("engine_options", {}),
        runtime_options=temp_record.get("runtime_options", {}),
    )


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


def _parse_recovery_state(raw: Any) -> RecoveryState:
    if isinstance(raw, RecoveryState):
        return raw
    if isinstance(raw, str):
        try:
            return RecoveryState(raw)
        except ValueError:
            return RecoveryState.NONE
    return RecoveryState.NONE
