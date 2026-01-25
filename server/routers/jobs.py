"""
API Router for Job Management.

Exposes endpoints for:
- Creating new jobs (POST /jobs)
- Querying job status (GET /jobs/{request_id})
- Uploading files to a job workspace (POST /jobs/{request_id}/upload)
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File  # type: ignore[import-not-found]
from fastapi.responses import FileResponse  # type: ignore[import-not-found]
from typing import Any
from ..models import (
    RunCreateRequest,
    RunCreateResponse,
    RunUploadResponse,
    RequestStatusResponse,
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
from ..services.cache_key_builder import compute_skill_fingerprint, compute_input_manifest_hash, compute_cache_key
from ..services.run_store import run_store
from ..services.run_cleanup_manager import run_cleanup_manager
import uuid
import json
from pathlib import Path

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("", response_model=RunCreateResponse)
async def create_run(request: RunCreateRequest, background_tasks: BackgroundTasks):
    # Verify skill exists
    skill = skill_registry.get_skill(request.skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{request.skill_id}' not found")
    if not skill.engines:
        raise HTTPException(status_code=400, detail=f"Skill '{request.skill_id}' does not declare supported engines")
    if request.engine not in skill.engines:
        raise HTTPException(
            status_code=400,
            detail=f"Skill '{request.skill_id}' does not support engine '{request.engine}'"
        )

    try:
        runtime_opts = options_policy.validate_runtime_options(request.runtime_options)
        engine_opts: dict[str, Any] = {}
        if request.model:
            validated = model_registry.validate_model(request.engine, request.model)
            engine_opts["model"] = validated["model"]
            if "model_reasoning_effort" in validated:
                engine_opts["model_reasoning_effort"] = validated["model_reasoning_effort"]

        request_id = str(uuid.uuid4())
        request_payload = request.model_dump()
        request_payload["engine_options"] = engine_opts
        request_payload["runtime_options"] = runtime_opts
        workspace_manager.create_request(request_id, request_payload)
        run_store.create_request(
            request_id=request_id,
            skill_id=request.skill_id,
            engine=request.engine,
            parameter=request.parameter,
            engine_options=engine_opts,
            runtime_options=runtime_opts
        )

        has_input_schema = bool(skill.schemas and "input" in skill.schemas)
        no_cache = bool(runtime_opts.get("no_cache"))
        if not has_input_schema:
            manifest_path = workspace_manager.write_input_manifest(request_id)
            manifest_hash = compute_input_manifest_hash(json.loads(manifest_path.read_text()))
            skill_fingerprint = compute_skill_fingerprint(skill, request.engine)
            cache_key = compute_cache_key(
                skill_id=request.skill_id,
                engine=request.engine,
                skill_fingerprint=skill_fingerprint,
                parameter=request.parameter,
                engine_options=engine_opts,
                input_manifest_hash=manifest_hash
            )
            run_store.update_request_manifest(request_id, str(manifest_path), manifest_hash)
            run_store.update_request_cache_key(request_id, cache_key, skill_fingerprint)
            if not no_cache:
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
                parameter=request.parameter,
                model=request.model,
                runtime_options=runtime_opts
            )
            run_status = workspace_manager.create_run(run_request)
            run_store.create_run(run_status.run_id, cache_key, RunStatus.QUEUED)
            run_store.update_request_run_id(request_id, run_status.run_id)
            merged_options = {**engine_opts, **runtime_opts}
            background_tasks.add_task(
                job_orchestrator.run_job,
                run_id=run_status.run_id,
                skill_id=request.skill_id,
                engine_name=request.engine,
                options=merged_options,
                cache_key=cache_key
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

    return RequestStatusResponse(
        request_id=request_id,
        status=current_status, 
        skill_id=skill_id,
        engine=engine,
        created_at=created_at,
        updated_at=updated_at_dt,
        warnings=warnings,
        error=error
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
            input_manifest_hash=manifest_hash
        )
        run_store.update_request_manifest(request_id, str(manifest_path), manifest_hash)
        run_store.update_request_cache_key(request_id, cache_key, skill_fingerprint)
        no_cache = bool(request_record.get("runtime_options", {}).get("no_cache"))
        if not no_cache:
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
                parameter=request_record["parameter"],
                model=request_record["engine_options"].get("model"),
                runtime_options=request_record["runtime_options"]
            )
        )
        workspace_manager.promote_request_uploads(request_id, run_status.run_id)
        run_store.create_run(run_status.run_id, cache_key, RunStatus.QUEUED)
        run_store.update_request_run_id(request_id, run_status.run_id)
        merged_options = {**request_record["engine_options"], **request_record["runtime_options"]}
        background_tasks.add_task(
            job_orchestrator.run_job,
            run_id=run_status.run_id,
            skill_id=request_record["skill_id"],
            engine_name=request_record["engine"],
            options=merged_options,
            cache_key=cache_key
        )
        return RunUploadResponse(
            request_id=request_id,
            cache_hit=False,
            extracted_files=result["extracted_files"]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
