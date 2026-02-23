from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from server.services.skill_patcher import COMPLETION_CONTRACT_MARKER, skill_patcher


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
    appended_completion_contract: bool


def _append_completion_contract_if_missing(skill_md_path: Path) -> bool:
    if not skill_md_path.exists():
        return False
    current = skill_md_path.read_text(encoding="utf-8")
    if COMPLETION_CONTRACT_MARKER in current:
        return False
    completion_patch = skill_patcher.generate_completion_contract_patch().strip()
    if not completion_patch:
        return False
    updated = current.rstrip()
    if updated:
        updated = f"{updated}\n\n{completion_patch}\n"
    else:
        updated = f"{completion_patch}\n"
    skill_md_path.write_text(updated, encoding="utf-8")
    return True


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


def inject_all_skill_packages(
    *,
    project_root: Path,
    run_directory: Path,
    engine: str,
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
            "appended_completion_contract_count": 0,
        }

    source_roots = [
        (project_root / "skills").resolve(),
        (project_root / "tests" / "fixtures" / "skills").resolve(),
    ]
    target_root = (run_directory / mapped).resolve()
    target_root.mkdir(parents=True, exist_ok=True)

    injected: list[InjectedSkillRecord] = []
    appended_count = 0
    for source_root in source_roots:
        for source_dir in _iter_skill_directories(source_root):
            target_dir = target_root / source_dir.name
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(source_dir, target_dir)
            target_skill_path = target_dir / "SKILL.md"
            appended = _append_completion_contract_if_missing(target_skill_path)
            if appended:
                appended_count += 1
            injected.append(
                InjectedSkillRecord(
                    skill_name=source_dir.name,
                    source_directory=source_dir,
                    target_directory=target_dir,
                    target_skill_path=target_skill_path,
                    appended_completion_contract=appended,
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
                "appended_completion_contract": item.appended_completion_contract,
            }
            for item in injected
        ],
        "appended_completion_contract_count": appended_count,
    }
