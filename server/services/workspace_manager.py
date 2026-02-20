import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from ..config import config
from ..models import RunCreateRequest, RunResponse, RunStatus, SkillManifest
from .engine_policy import resolve_skill_engine_policy

import zipfile
import io
class WorkspaceManager:
    """
    Manages the filesystem workspace for execution runs.
    
    Responsibilities:
    - Creates unique run directories (`runs/{uuid}`).
    - Provisions subdirectories (`logs`, `artifacts`, `result`).
    - Handles file uploads to the workspace.
    - Provides accessors for run paths.
    """
    def create_run(self, request: RunCreateRequest) -> RunResponse:
        from .skill_registry import skill_registry
        skill = skill_registry.get_skill(request.skill_id)
        if not skill:
            raise ValueError(f"Skill '{request.skill_id}' not found")
        self._validate_skill_engine(skill, request.engine)
        return self._create_run_dir_and_metadata(request)

    def create_run_for_skill(self, request: RunCreateRequest, skill: SkillManifest) -> RunResponse:
        self._validate_skill_engine(skill, request.engine)
        return self._create_run_dir_and_metadata(request)

    def _validate_skill_engine(self, skill: SkillManifest, engine: str) -> None:
        policy = resolve_skill_engine_policy(skill)
        if engine not in policy.effective_engines:
            raise ValueError(
                f"Skill '{skill.id}' does not support engine '{engine}'"
            )

    def _create_run_dir_and_metadata(self, request: RunCreateRequest) -> RunResponse:
        run_id = str(uuid.uuid4())
        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (run_dir / "logs").mkdir()
        (run_dir / "artifacts").mkdir()
        (run_dir / "raw").mkdir()
        (run_dir / "result").mkdir()
        (run_dir / "interactions").mkdir()
        # uploads directory is created only when inputs are promoted

        # Save input
        with open(run_dir / "input.json", 'w', encoding='utf-8') as f:
            json.dump(request.model_dump(), f, indent=2)

        # Initial status
        now = datetime.now()
        status = RunResponse(
            run_id=run_id,
            status=RunStatus.QUEUED,
            skill_id=request.skill_id,
            engine=request.engine,
            created_at=now,
            updated_at=now
        )
        
        # Save initial status backup (optional, for persistent state)
        # In v0 we might just keep in memory or rely on filesystem existence
        
        return status

    def create_request(self, request_id: str, request_payload: Dict[str, Any]) -> Path:
        request_dir = Path(config.SYSTEM.REQUESTS_DIR) / request_id
        request_dir.mkdir(parents=True, exist_ok=True)
        (request_dir / "uploads").mkdir()

        with open(request_dir / "request.json", "w", encoding="utf-8") as f:
            json.dump(request_payload, f, indent=2)

        return request_dir

    def get_request_dir(self, request_id: str) -> Optional[Path]:
        path = Path(config.SYSTEM.REQUESTS_DIR) / request_id
        return path if path.exists() else None

    def get_run_dir(self, run_id: str) -> Optional[Path]:
        path = Path(config.SYSTEM.RUNS_DIR) / run_id
        return path if path.exists() else None

    def handle_upload(self, request_id: str, file_bytes: bytes) -> Dict[str, Any]:
        request_dir = self.get_request_dir(request_id)
        if not request_dir:
            raise ValueError(f"Request {request_id} not found")
            
        uploads_dir = request_dir / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                z.extractall(uploads_dir)
            
            # Return list of extracted files
            extracted = [str(p.relative_to(uploads_dir)) for p in uploads_dir.rglob("*") if p.is_file()]
            return {"status": "success", "extracted_files": extracted}
        except zipfile.BadZipFile:
            raise ValueError("Invalid zip file")

    def write_input_manifest(self, request_id: str) -> Path:
        request_dir = self.get_request_dir(request_id)
        if not request_dir:
            raise ValueError(f"Request {request_id} not found")

        from .cache_key_builder import build_input_manifest

        uploads_dir = request_dir / "uploads"
        manifest = build_input_manifest(uploads_dir)
        manifest_path = request_dir / "input_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return manifest_path

    def promote_request_uploads(self, request_id: str, run_id: str) -> None:
        request_dir = self.get_request_dir(request_id)
        run_dir = self.get_run_dir(run_id)
        if not request_dir:
            raise ValueError(f"Request {request_id} not found")
        if not run_dir:
            raise ValueError(f"Run {run_id} not found")

        from shutil import move

        source_dir = request_dir / "uploads"
        target_dir = run_dir / "uploads"
        if target_dir.exists():
            raise ValueError(f"Run uploads already exist for {run_id}")
        if source_dir.exists():
            move(str(source_dir), str(target_dir))

    def delete_run_dir(self, run_id: str) -> None:
        run_dir = self.get_run_dir(run_id)
        if run_dir and run_dir.exists():
            from shutil import rmtree
            rmtree(run_dir, ignore_errors=True)

    def delete_request_dir(self, request_id: str) -> None:
        request_dir = self.get_request_dir(request_id)
        if request_dir and request_dir.exists():
            from shutil import rmtree
            rmtree(request_dir, ignore_errors=True)

    def purge_runs_dir(self) -> None:
        runs_dir = Path(config.SYSTEM.RUNS_DIR)
        runs_dir.mkdir(parents=True, exist_ok=True)
        for entry in runs_dir.iterdir():
            if entry.is_dir():
                self.delete_run_dir(entry.name)
            else:
                entry.unlink(missing_ok=True)

    def purge_requests_dir(self) -> None:
        requests_dir = Path(config.SYSTEM.REQUESTS_DIR)
        requests_dir.mkdir(parents=True, exist_ok=True)
        for entry in requests_dir.iterdir():
            if entry.is_dir():
                self.delete_request_dir(entry.name)
            else:
                entry.unlink(missing_ok=True)


workspace_manager = WorkspaceManager()
