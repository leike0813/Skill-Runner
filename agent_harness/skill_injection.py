from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Literal

from server.models import ManifestArtifact
from server.services.orchestration.manifest_artifact_inference import infer_manifest_artifacts
from server.services.skill.skill_patcher import skill_patcher


AGENT_SKILL_ROOTS: dict[str, Path] = {
    "codex": Path(".codex/skills"),
    "gemini": Path(".gemini/skills"),
    "iflow": Path(".iflow/skills"),
    "opencode": Path(".opencode/skills"),
}


@dataclass(frozen=True)
class InjectedSkillRecord:
    skill_name: str
    source_directory: Path
    target_directory: Path
    target_skill_path: Path
    patched: bool


def _iter_skill_directories(source_root: Path) -> list[Path]:
    if not source_root.exists() or not source_root.is_dir():
        return []
    skill_dirs: list[Path] = []
    for entry in sorted(source_root.iterdir(), key=lambda item: item.name):
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue
        if not (entry / "SKILL.md").exists():
            continue
        skill_dirs.append(entry)
    return skill_dirs


def _load_manifest_artifacts(skill_dir: Path) -> List[ManifestArtifact]:
    runner_path = skill_dir / "assets" / "runner.json"
    if not runner_path.exists() or not runner_path.is_file():
        return []
    try:
        payload = json.loads(runner_path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Failed to parse runner manifest for skill injection: %s", runner_path)
        return []
    if not isinstance(payload, dict):
        return []
    enriched = infer_manifest_artifacts(payload, skill_dir)
    artifacts_raw = enriched.get("artifacts")
    if not isinstance(artifacts_raw, list):
        return []
    artifacts: List[ManifestArtifact] = []
    for item in artifacts_raw:
        try:
            artifacts.append(ManifestArtifact.model_validate(item))
        except Exception:
            logger.warning("Ignore invalid artifact entry in %s: %r", runner_path, item)
    return artifacts


def inject_all_skill_packages(
    *,
    project_root: Path,
    run_directory: Path,
    engine: str,
    execution_mode: Literal["auto", "interactive"],
) -> dict[str, Any]:
    mapped = AGENT_SKILL_ROOTS.get(engine)
    if mapped is None:
        return {
            "mode": "all",
            "engine": engine,
            "supported": False,
            "source_roots": [],
            "target_root": "",
            "skill_count": 0,
            "skills": [],
            "injected_skills": [],
            "patched_skill_count": 0,
        }

    source_roots = [
        (project_root / "skills").resolve(),
        (project_root / "tests" / "fixtures" / "skills").resolve(),
    ]
    target_root = (run_directory / mapped).resolve()
    target_root.mkdir(parents=True, exist_ok=True)

    injected: list[InjectedSkillRecord] = []
    patched_count = 0
    for source_root in source_roots:
        for source_dir in _iter_skill_directories(source_root):
            target_dir = target_root / source_dir.name
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(source_dir, target_dir)
            target_skill_path = target_dir / "SKILL.md"
            patched = skill_patcher.patch_skill_md(
                target_dir,
                artifacts=_load_manifest_artifacts(target_dir),
                execution_mode=execution_mode,
            )
            if patched:
                patched_count += 1
            injected.append(
                InjectedSkillRecord(
                    skill_name=source_dir.name,
                    source_directory=source_dir,
                    target_directory=target_dir,
                    target_skill_path=target_skill_path,
                    patched=patched,
                )
            )

    return {
        "mode": "all",
        "engine": engine,
        "supported": True,
        "source_roots": [str(path) for path in source_roots],
        "target_root": str(target_root),
        "skill_count": len(injected),
        "skills": [item.skill_name for item in injected],
        "injected_skills": [
            {
                "skill_name": item.skill_name,
                "source_directory": str(item.source_directory),
                "target_directory": str(item.target_directory),
                "target_skill_path": str(item.target_skill_path),
                "patched": item.patched,
            }
            for item in injected
        ],
        "patched_skill_count": patched_count,
    }


logger = logging.getLogger(__name__)
