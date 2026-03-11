from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ....models import SkillManifest
from ....services.skill.skill_asset_resolver import resolve_schema_asset
from ..contracts import AdapterExecutionContext
from .profile_loader import AdapterProfile


def validate_run_folder_contract(
    *,
    skill: SkillManifest,
    config_path: Path,
) -> Path:
    if not config_path.exists():
        raise RuntimeError(f"RUN_FOLDER_INVALID: missing config file: {config_path}")

    skill_path = skill.path
    if skill_path is None:
        raise RuntimeError(f"RUN_FOLDER_INVALID: missing materialized skill path for '{skill.id}'")

    skill_dir = skill_path.resolve()
    if not skill_dir.exists() or not skill_dir.is_dir():
        raise RuntimeError(f"RUN_FOLDER_INVALID: missing skill directory: {skill_dir}")

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise RuntimeError(f"RUN_FOLDER_INVALID: missing SKILL.md: {skill_md}")

    runner_path = skill_dir / "assets" / "runner.json"
    if not runner_path.exists():
        raise RuntimeError(f"RUN_FOLDER_INVALID: missing assets/runner.json: {runner_path}")
    try:
        runner = json.loads(runner_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeError(f"RUN_FOLDER_INVALID: unreadable assets/runner.json: {runner_path}") from exc
    if not isinstance(runner, dict):
        raise RuntimeError(f"RUN_FOLDER_INVALID: runner.json must be an object: {runner_path}")

    for schema_key in ("input", "parameter", "output"):
        resolution = resolve_schema_asset(
            SkillManifest(id=skill.id, path=skill_dir, schemas=runner.get("schemas")),
            schema_key,
        )
        if resolution.path is None:
            raise RuntimeError(
                f"RUN_FOLDER_INVALID: missing schema file '{schema_key}': "
                f"{resolution.fallback_relpath or resolution.declared_relpath or runner_path}"
            )

    return skill_dir


class ProfiledAttemptRunFolderValidator:
    def __init__(self, *, adapter: Any, profile: AdapterProfile) -> None:
        self._adapter = adapter
        self._profile = profile

    def validate(self, ctx: AdapterExecutionContext, config_path: Path) -> Path:
        skill = ctx.skill
        if skill.path is None and self._profile.attempt_workspace.unknown_fallback:
            return self._profile.skills_root_from(run_dir=ctx.run_dir, config_path=config_path) / "unknown"
        return validate_run_folder_contract(skill=skill, config_path=config_path)
