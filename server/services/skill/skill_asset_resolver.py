from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from server.models import SkillManifest


ResolutionIssueCode = Literal[
    "missing_declaration",
    "empty_declaration",
    "invalid_declaration_type",
    "absolute_path",
    "path_escape",
    "target_not_found",
]


@dataclass(frozen=True)
class SkillAssetResolution:
    path: Path | None
    declared_relpath: str | None
    fallback_relpath: str | None
    used_fallback: bool
    issue_code: ResolutionIssueCode | None
    issue_source: Literal["declared", "fallback", "none"]


def load_runner_manifest(skill_root: Path) -> dict[str, Any] | None:
    runner_path = skill_root / "assets" / "runner.json"
    if not runner_path.exists() or not runner_path.is_file():
        return None
    try:
        payload = json.loads(runner_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def resolve_schema_asset(skill: SkillManifest, schema_key: str) -> SkillAssetResolution:
    fallback_relpath = f"assets/{schema_key}.schema.json"
    declared_relpath: str | None = None
    if isinstance(skill.schemas, dict):
        raw = skill.schemas.get(schema_key)
        if isinstance(raw, str):
            declared_relpath = raw
        elif raw is not None:
            declared_relpath = ""
    return _resolve_skill_asset(
        skill_root=skill.path,
        declared_relpath=declared_relpath,
        fallback_relpath=fallback_relpath,
    )


def resolve_engine_config_asset(
    skill: SkillManifest,
    engine: str,
    fallback_relpath: str | None,
) -> SkillAssetResolution:
    declared_relpath: str | None = None
    engine_configs = getattr(skill, "engine_configs", None)
    if isinstance(engine_configs, dict):
        raw = engine_configs.get(engine)
        if isinstance(raw, str):
            declared_relpath = raw
        elif raw is not None:
            declared_relpath = ""
    return _resolve_skill_asset(
        skill_root=skill.path,
        declared_relpath=declared_relpath,
        fallback_relpath=fallback_relpath,
    )


def load_resolved_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _resolve_skill_asset(
    *,
    skill_root: Path | None,
    declared_relpath: str | None,
    fallback_relpath: str | None,
) -> SkillAssetResolution:
    if skill_root is None:
        return SkillAssetResolution(
            path=None,
            declared_relpath=declared_relpath,
            fallback_relpath=fallback_relpath,
            used_fallback=False,
            issue_code="missing_declaration",
            issue_source="none",
        )

    try:
        root_resolved = skill_root.resolve(strict=True)
    except FileNotFoundError:
        return SkillAssetResolution(
            path=None,
            declared_relpath=declared_relpath,
            fallback_relpath=fallback_relpath,
            used_fallback=False,
            issue_code="target_not_found",
            issue_source="none",
        )

    if declared_relpath is not None:
        declared_path, declared_issue = _resolve_relative_path(root_resolved, declared_relpath)
        if declared_path is not None:
            return SkillAssetResolution(
                path=declared_path,
                declared_relpath=declared_relpath,
                fallback_relpath=fallback_relpath,
                used_fallback=False,
                issue_code=None,
                issue_source="none",
            )
        fallback_path, _ = _resolve_fallback(root_resolved, fallback_relpath)
        return SkillAssetResolution(
            path=fallback_path,
            declared_relpath=declared_relpath,
            fallback_relpath=fallback_relpath,
            used_fallback=fallback_path is not None,
            issue_code=declared_issue,
            issue_source="declared",
        )

    fallback_path, fallback_issue = _resolve_fallback(root_resolved, fallback_relpath)
    return SkillAssetResolution(
        path=fallback_path,
        declared_relpath=None,
        fallback_relpath=fallback_relpath,
        used_fallback=fallback_path is not None,
        issue_code=fallback_issue if fallback_path is None else None,
        issue_source="fallback" if fallback_path is None and fallback_issue is not None else "none",
    )


def _resolve_fallback(
    root_resolved: Path,
    fallback_relpath: str | None,
) -> tuple[Path | None, ResolutionIssueCode | None]:
    if not isinstance(fallback_relpath, str) or not fallback_relpath.strip():
        return None, "missing_declaration"
    return _resolve_relative_path(root_resolved, fallback_relpath)


def _resolve_relative_path(
    root_resolved: Path,
    raw_relpath: str,
) -> tuple[Path | None, ResolutionIssueCode | None]:
    stripped = raw_relpath.strip()
    if not stripped:
        return None, "empty_declaration"

    requested = Path(stripped)
    if requested.is_absolute():
        return None, "absolute_path"

    candidate = (root_resolved / requested).resolve(strict=False)
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None, "path_escape"

    if not candidate.exists() or not candidate.is_file():
        return None, "target_not_found"

    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        return None, "path_escape"
    return resolved, None
