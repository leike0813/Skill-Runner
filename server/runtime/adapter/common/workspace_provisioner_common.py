from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Iterable

from ....models import SkillManifest
from ....services.skill.skill_patcher import skill_patcher
from ..contracts import AdapterExecutionContext
from .profile_loader import AdapterProfile

logger = logging.getLogger(__name__)


def install_skill_package(
    *,
    skill: SkillManifest,
    skills_target_dir: Path,
    execution_mode: str,
    artifacts: Iterable[str] | None = None,
) -> Path:
    if skill.path:
        if skills_target_dir.exists():
            shutil.rmtree(skills_target_dir)
        try:
            shutil.copytree(skill.path, skills_target_dir)
            logger.info("Installed skill %s to %s", skill.id, skills_target_dir)
        except Exception:
            logger.exception("Failed to install skill package")

    output_schema_relpath = (
        str(skill.schemas.get("output"))
        if isinstance(skill.schemas, dict) and isinstance(skill.schemas.get("output"), str)
        else None
    )
    output_schema = skill_patcher.load_output_schema(
        skill_path=skill.path,
        output_schema_relpath=output_schema_relpath,
    )
    skill_patcher.patch_skill_md(
        skills_target_dir,
        list(artifacts or []),
        execution_mode=execution_mode,
        output_schema=output_schema,
    )
    return skills_target_dir


class ProfiledWorkspaceProvisioner:
    def __init__(self, *, adapter: Any, profile: AdapterProfile) -> None:
        self._adapter = adapter
        self._profile = profile

    def prepare(self, ctx: AdapterExecutionContext, config_path: Path) -> Path:
        skill = ctx.skill
        options = ctx.options
        skills_root = self._profile.skills_root_from(run_dir=ctx.run_dir, config_path=config_path)
        skills_target_dir = skills_root / skill.id
        if self._profile.workspace_provisioner.unknown_fallback and not skill.path:
            return skills_root / "unknown"
        return install_skill_package(
            skill=skill,
            skills_target_dir=skills_target_dir,
            execution_mode=self._adapter._resolve_execution_mode(options),  # noqa: SLF001
            artifacts=skill.artifacts or [],
        )
