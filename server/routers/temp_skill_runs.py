import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile  # type: ignore[import-not-found]
from fastapi.responses import FileResponse  # type: ignore[import-not-found]

from ..models import (
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
from ..services.temp_skill_run_manager import temp_skill_run_manager
from ..services.temp_skill_run_store import temp_skill_run_store
from ..services.workspace_manager import workspace_manager


router = APIRouter(prefix="/temp-skill-runs", tags=["temp-skill-runs"])


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
        workspace_manager.validate_skill_engine(skill, record["engine"])

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
    except HTTPException:
        if run_status is not None:
            temp_skill_run_store.update_status(request_id, RunStatus.FAILED, error="Job queue is full")
        elif record.get("run_id") is None:
            temp_skill_run_store.update_status(request_id, RunStatus.FAILED, error="Job queue is full")
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

    return RequestStatusResponse(
        request_id=request_id,
        status=status,
        skill_id=rec.get("skill_id") or "unknown",
        engine=rec.get("engine", "unknown"),
        created_at=created_at,
        updated_at=updated_at,
        warnings=warnings,
        error=error,
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
