import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional
from server.config import config
from server.models import RunCreateRequest, RunResponse, RunStatus, SkillManifest
from server.services.engine_management.engine_policy import resolve_skill_engine_policy

class WorkspaceManager:
    """
    Manages the filesystem workspace for execution runs.
    
    Responsibilities:
    - Creates unique run directories (`runs/{uuid}`).
    - Provisions canonical subdirectories (`artifacts`, `result`, `.state`, `.audit`).
    - Handles file uploads to the workspace.
    - Provides accessors for run paths.
    """
    def create_run(self, request: RunCreateRequest) -> RunResponse:
        from server.services.skill.skill_registry import skill_registry
        skill_id = request.skill_id
        if not isinstance(skill_id, str) or not skill_id.strip():
            raise ValueError("skill_id is required")
        skill = skill_registry.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill '{skill_id}' not found")
        self._validate_skill_engine(skill, request.engine)
        return self._create_run_dir_and_metadata(request, skill_id=skill_id)

    def create_run_for_skill(self, request: RunCreateRequest, skill: SkillManifest) -> RunResponse:
        self._validate_skill_engine(skill, request.engine)
        resolved_skill_id = (
            request.skill_id
            if isinstance(request.skill_id, str) and request.skill_id.strip()
            else skill.id
        )
        return self._create_run_dir_and_metadata(request, skill_id=resolved_skill_id)

    def _validate_skill_engine(self, skill: SkillManifest, engine: str) -> None:
        policy = resolve_skill_engine_policy(skill)
        if engine not in policy.effective_engines:
            raise ValueError(
                f"Skill '{skill.id}' does not support engine '{engine}'"
            )

    def _create_run_dir_and_metadata(self, request: RunCreateRequest, *, skill_id: str) -> RunResponse:
        run_id = str(uuid.uuid4())
        run_dir = Path(config.SYSTEM.RUNS_DIR) / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # Create canonical subdirectories
        (run_dir / "artifacts").mkdir()
        (run_dir / "result").mkdir()
        (run_dir / ".state").mkdir()
        (run_dir / ".audit").mkdir()
        # uploads directory is created only when inputs are promoted

        # Initial status
        now = datetime.now()
        status = RunResponse(
            run_id=run_id,
            status=RunStatus.QUEUED,
            skill_id=skill_id,
            engine=request.engine,
            created_at=now,
            updated_at=now
        )
        
        # Save initial status backup (optional, for persistent state)
        # In v0 we might just keep in memory or rely on filesystem existence
        
        return status

    def get_run_dir(self, run_id: str) -> Optional[Path]:
        path = Path(config.SYSTEM.RUNS_DIR) / run_id
        return path if path.exists() else None

    def delete_run_dir(self, run_id: str) -> None:
        run_dir = self.get_run_dir(run_id)
        if run_dir and run_dir.exists():
            from shutil import rmtree
            rmtree(run_dir, ignore_errors=True)

    def purge_runs_dir(self) -> None:
        runs_dir = Path(config.SYSTEM.RUNS_DIR)
        runs_dir.mkdir(parents=True, exist_ok=True)
        for entry in runs_dir.iterdir():
            if entry.is_dir():
                self.delete_run_dir(entry.name)
            else:
                entry.unlink(missing_ok=True)


workspace_manager = WorkspaceManager()
