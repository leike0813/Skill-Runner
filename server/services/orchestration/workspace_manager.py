import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional
from server.config import config
from server.models import RunCreateRequest, RunResponse, RunStatus, SkillManifest
from server.services.engine_management.engine_policy import resolve_skill_engine_policy
from server.services.orchestration.run_workspace_layout import safe_segment

class WorkspaceManager:
    """
    Manages the filesystem workspace for execution runs.
    
    Responsibilities:
    - Creates unique physical workspace directories (`workspaces/{uuid}`).
    - Provisions canonical subdirectories (`artifacts`, `result`, `.state`, `.audit`).
    - Handles file uploads to the workspace.
    - Provides legacy accessors for historical run paths.
    """
    def create_run(
        self,
        request: RunCreateRequest,
        *,
        workspace_dir: Path | None = None,
    ) -> RunResponse:
        from server.services.skill.skill_registry import skill_registry
        skill_id = request.skill_id
        if not isinstance(skill_id, str) or not skill_id.strip():
            raise ValueError("skill_id is required")
        skill = skill_registry.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill '{skill_id}' not found")
        self._validate_skill_engine(skill, request.engine)
        return self._create_run_dir_and_metadata(request, skill_id=skill_id, workspace_dir=workspace_dir)

    def create_run_for_skill(
        self,
        request: RunCreateRequest,
        skill: SkillManifest,
        *,
        workspace_dir: Path | None = None,
    ) -> RunResponse:
        self._validate_skill_engine(skill, request.engine)
        resolved_skill_id = (
            request.skill_id
            if isinstance(request.skill_id, str) and request.skill_id.strip()
            else skill.id
        )
        return self._create_run_dir_and_metadata(
            request,
            skill_id=resolved_skill_id,
            workspace_dir=workspace_dir,
        )

    def _validate_skill_engine(self, skill: SkillManifest, engine: str) -> None:
        policy = resolve_skill_engine_policy(skill)
        if engine not in policy.effective_engines:
            raise ValueError(
                f"Skill '{skill.id}' does not support engine '{engine}'"
            )

    def _create_run_dir_and_metadata(
        self,
        request: RunCreateRequest,
        *,
        skill_id: str,
        workspace_dir: Path | None = None,
    ) -> RunResponse:
        run_id = str(uuid.uuid4())
        if workspace_dir is not None:
            resolved_workspace_dir = workspace_dir.resolve()
            if not resolved_workspace_dir.exists() or not resolved_workspace_dir.is_dir():
                raise ValueError("workspace reuse target does not exist")
            workspace_id = resolved_workspace_dir.name
        else:
            workspace_id = run_id
            resolved_workspace_dir = (Path(config.SYSTEM.WORKSPACES_DIR) / workspace_id).resolve()
            resolved_workspace_dir.mkdir(parents=True, exist_ok=True)

        # Create canonical subdirectories in the physical workspace.
        (resolved_workspace_dir / "uploads").mkdir(exist_ok=True)
        (resolved_workspace_dir / "artifacts").mkdir(exist_ok=True)
        (resolved_workspace_dir / "result").mkdir(exist_ok=True)
        (resolved_workspace_dir / ".state").mkdir(exist_ok=True)
        (resolved_workspace_dir / ".audit").mkdir(exist_ok=True)
        (resolved_workspace_dir / "bundle").mkdir(exist_ok=True)

        # Initial status
        now = datetime.now()
        status = RunResponse(
            run_id=run_id,
            status=RunStatus.QUEUED,
            skill_id=skill_id,
            engine=request.engine,
            created_at=now,
            updated_at=now,
            workspace_id=workspace_id,
            workspace_dir=str(resolved_workspace_dir),
        )
        
        # Save initial status backup (optional, for persistent state)
        # In v0 we might just keep in memory or rely on filesystem existence
        
        return status

    def get_legacy_run_dir(self, run_id: str) -> Optional[Path]:
        """Return legacy data/runs directory for historical no-layout records only."""
        patched_get_run_dir = self.__dict__.get("get_run_dir")
        if (
            callable(patched_get_run_dir)
            and getattr(patched_get_run_dir, "__func__", None) is not WorkspaceManager.get_run_dir
        ):
            return patched_get_run_dir(run_id)
        path = Path(config.SYSTEM.RUNS_DIR) / run_id
        return path if path.exists() else None

    def get_run_dir(self, run_id: str) -> Optional[Path]:
        """Compatibility wrapper for legacy no-layout callers."""
        return self.get_legacy_run_dir(run_id)

    def get_workspace_dir(self, workspace_id: str) -> Optional[Path]:
        path = Path(config.SYSTEM.WORKSPACES_DIR) / workspace_id
        return path if path.exists() else None

    def allocate_namespace(self, *, workspace_dir: Path, skill_id: str) -> str:
        safe_skill_id = safe_segment(skill_id, "skill")
        highest = 0
        result_dir = workspace_dir / "result"
        if result_dir.exists():
            for entry in result_dir.iterdir():
                if not entry.is_dir():
                    continue
                name = entry.name
                prefix = f"{safe_skill_id}."
                if not name.startswith(prefix):
                    continue
                suffix = name[len(prefix):]
                try:
                    highest = max(highest, int(suffix))
                except ValueError:
                    continue
        return f"{safe_skill_id}.{highest + 1}"

    def delete_run_dir(self, run_id: str) -> None:
        run_dir = self.get_legacy_run_dir(run_id)
        if run_dir and run_dir.exists():
            from shutil import rmtree
            if run_dir.is_symlink():
                run_dir.unlink(missing_ok=True)
            else:
                rmtree(run_dir, ignore_errors=True)

    def delete_workspace_dir(self, workspace_dir: Path) -> None:
        from shutil import rmtree

        target = workspace_dir.resolve()
        workspaces_root = Path(config.SYSTEM.WORKSPACES_DIR).resolve()
        try:
            target.relative_to(workspaces_root)
        except ValueError:
            return
        if target.exists() and target.is_dir():
            rmtree(target, ignore_errors=True)

    def purge_runs_dir(self) -> None:
        runs_dir = Path(config.SYSTEM.RUNS_DIR)
        runs_dir.mkdir(parents=True, exist_ok=True)
        for entry in runs_dir.iterdir():
            if entry.is_dir():
                self.delete_run_dir(entry.name)
            else:
                entry.unlink(missing_ok=True)

    def purge_workspaces_dir(self) -> None:
        from shutil import rmtree

        workspaces_dir = Path(config.SYSTEM.WORKSPACES_DIR)
        if workspaces_dir.exists():
            rmtree(workspaces_dir, ignore_errors=True)
        workspaces_dir.mkdir(parents=True, exist_ok=True)


workspace_manager = WorkspaceManager()
