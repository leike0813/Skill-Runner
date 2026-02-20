import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, Request, UploadFile  # type: ignore[import-not-found]
from fastapi.responses import FileResponse, StreamingResponse  # type: ignore[import-not-found]

from ..models import (
    CancelResponse,
    ExecutionMode,
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
from ..services.options_policy import options_policy
from ..services.run_observability import run_observability_service
from ..services.run_store import run_store
from ..services.temp_skill_run_manager import temp_skill_run_manager
from ..services.temp_skill_run_store import temp_skill_run_store
from ..services.workspace_manager import workspace_manager
from ..services.engine_policy import SkillEnginePolicy, resolve_skill_engine_policy


router = APIRouter(prefix="/temp-skill-runs", tags=["temp-skill-runs"])

TERMINAL_STATUSES = {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELED}
ACTIVE_CANCELABLE_STATUSES = {RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.WAITING_USER}


@router.post("", response_model=TempSkillRunCreateResponse)
async def create_temp_skill_run(request: TempSkillRunCreateRequest):
    try:
        runtime_opts = options_policy.validate_runtime_options(request.runtime_options)
        engine_opts: dict[str, Any] = {}
        if request.model:
            validated = model_registry.validate_model(request.engine, request.model)
            engine_opts["model"] = validated["model"]
            if "model_reasoning_effort" in validated:
                engine_opts["model_reasoning_effort"] = validated["model_reasoning_effort"]

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
        skill = temp_skill_run_manager.stage_skill_package(request_id, skill_bytes)
        engine_policy = resolve_skill_engine_policy(skill)
        _ensure_skill_engine_supported(
            skill_id=skill.id,
            requested_engine=record["engine"],
            policy=engine_policy,
        )
        requested_mode = record.get("runtime_options", {}).get(
            "execution_mode", ExecutionMode.AUTO.value
        )
        declared_modes = _declared_execution_modes(skill)
        if requested_mode not in declared_modes:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "SKILL_EXECUTION_MODE_UNSUPPORTED",
                    "message": (
                        f"Skill '{skill.id}' does not support execution_mode "
                        f"'{requested_mode}'"
                    ),
                    "declared_execution_modes": sorted(declared_modes),
                    "requested_execution_mode": requested_mode,
                },
            )

        if file is not None:
            input_bytes = await file.read()
            upload_res = workspace_manager.handle_upload(request_id, input_bytes)
            extracted_files = upload_res.get("extracted_files", [])

        run_request = RunCreateRequest(
            skill_id=skill.id,
            engine=record["engine"],
            parameter=record["parameter"],
            model=record.get("model"),
            runtime_options=record["runtime_options"],
        )
        run_status = workspace_manager.create_run_for_skill(run_request, skill)
        workspace_manager.promote_request_uploads(request_id, run_status.run_id)
        temp_skill_run_store.update_run_started(request_id, run_status.run_id)

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
            cache_key=None,
            skill_override=skill,
            temp_request_id=request_id,
        )
        return TempSkillRunUploadResponse(
            request_id=request_id,
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
        return RequestStatusResponse(
            request_id=request_id,
            status=RunStatus(rec.get("status", RunStatus.QUEUED.value)),
            skill_id=rec.get("skill_id") or "unknown",
            engine=rec.get("engine", "unknown"),
            created_at=created_at,
            updated_at=updated_at,
            warnings=[],
            error={"message": rec["error"]} if rec.get("error") else None,
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

    return RequestStatusResponse(
        request_id=request_id,
        status=status,
        skill_id=rec.get("skill_id") or "unknown",
        engine=rec.get("engine", "unknown"),
        created_at=created_at,
        updated_at=updated_at,
        warnings=warnings,
        error=error,
        recovery_state=_parse_recovery_state(recovery_info.get("recovery_state")),
        recovered_at=recovered_at,
        recovery_reason=_coerce_str_or_none(recovery_info.get("recovery_reason")),
    )


@router.get("/{request_id}/result", response_model=RunResultResponse)
async def get_temp_skill_run_result(request_id: str):
    run_dir = _get_run_dir_from_temp_request(request_id)
    result_path = run_dir / "result" / "result.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Run result not found")
    return RunResultResponse(
        request_id=request_id,
        result=json.loads(result_path.read_text(encoding="utf-8")),
    )


@router.get("/{request_id}/artifacts", response_model=RunArtifactsResponse)
async def get_temp_skill_run_artifacts(request_id: str):
    run_dir = _get_run_dir_from_temp_request(request_id)
    artifacts: list[str] = []
    artifacts_dir = run_dir / "artifacts"
    if artifacts_dir.exists():
        for path in artifacts_dir.rglob("*"):
            if path.is_file():
                artifacts.append(path.relative_to(run_dir).as_posix())
    return RunArtifactsResponse(request_id=request_id, artifacts=artifacts)


@router.get("/{request_id}/bundle")
async def get_temp_skill_run_bundle(request_id: str):
    rec = temp_skill_run_store.get_request(request_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Request not found")
    run_dir = _get_run_dir_from_temp_request(request_id)
    debug_mode = bool(rec.get("runtime_options", {}).get("debug"))
    bundle_name = "run_bundle_debug.zip" if debug_mode else "run_bundle.zip"
    bundle_path = run_dir / "bundle" / bundle_name
    if not bundle_path.exists():
        job_orchestrator._build_run_bundle(run_dir, debug_mode)
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="Bundle not found")
    return FileResponse(path=bundle_path, filename=bundle_path.name)


@router.get("/{request_id}/artifacts/{artifact_path:path}")
async def download_temp_skill_artifact(request_id: str, artifact_path: str):
    run_dir = _get_run_dir_from_temp_request(request_id)
    if not artifact_path:
        raise HTTPException(status_code=400, detail="Artifact path is required")
    if not artifact_path.startswith("artifacts/"):
        raise HTTPException(status_code=404, detail="Artifact not found")
    target = (run_dir / artifact_path).resolve()
    artifacts_root = (run_dir / "artifacts").resolve()
    if not str(target).startswith(str(artifacts_root)):
        raise HTTPException(status_code=400, detail="Invalid artifact path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path=target, filename=target.name)


@router.get("/{request_id}/logs", response_model=RunLogsResponse)
async def get_temp_skill_run_logs(request_id: str):
    run_dir = _get_run_dir_from_temp_request(request_id)
    logs_dir = run_dir / "logs"
    if not logs_dir.exists():
        return RunLogsResponse(request_id=request_id)

    return RunLogsResponse(
        request_id=request_id,
        prompt=_read_log(logs_dir / "prompt.txt"),
        stdout=_read_log(logs_dir / "stdout.txt"),
        stderr=_read_log(logs_dir / "stderr.txt"),
    )


@router.post("/{request_id}/cancel", response_model=CancelResponse)
async def cancel_temp_skill_run(request_id: str):
    rec = temp_skill_run_store.get_request(request_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Request not found")
    run_id_obj = rec.get("run_id")
    if not isinstance(run_id_obj, str) or not run_id_obj:
        raise HTTPException(status_code=404, detail="Run not found")
    run_id = run_id_obj
    run_dir = _get_run_dir_from_temp_request(request_id)

    status = RunStatus(rec.get("status", RunStatus.QUEUED.value))
    status_file = run_dir / "status.json"
    if status_file.exists():
        payload = json.loads(status_file.read_text(encoding="utf-8"))
        status = RunStatus(payload.get("status", status.value))

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
        engine_name=str(rec.get("engine", "")),
        run_dir=run_dir,
        status=status,
        temp_request_id=request_id,
    )
    return CancelResponse(
        request_id=request_id,
        run_id=run_id,
        status=RunStatus.CANCELED,
        accepted=accepted,
        message="Cancel request accepted" if accepted else "Cancel already requested",
    )


@router.get("/{request_id}/events")
async def stream_temp_skill_run_events(
    request_id: str,
    request: Request,
    stdout_from: int = Query(default=0, ge=0),
    stderr_from: int = Query(default=0, ge=0),
):
    run_dir = _get_run_dir_from_temp_request(request_id)

    async def _event_stream():
        async for item in run_observability_service.iter_sse_events(
            run_dir=run_dir,
            request_id=None,
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


def _get_run_dir_from_temp_request(request_id: str) -> Path:
    rec = temp_skill_run_store.get_request(request_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Request not found")
    run_id = rec.get("run_id")
    if not run_id:
        raise HTTPException(status_code=404, detail="Run not found")
    run_dir = workspace_manager.get_run_dir(run_id)
    if not run_dir:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_dir


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
            "unsupported_engines": policy.unsupported_engines,
            "effective_engines": policy.effective_engines,
            "requested_engine": requested_engine,
        },
    )


def _read_log(path: Path) -> str | None:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def _parse_dt(raw: str | None) -> datetime:
    if not raw:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.utcnow()


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
