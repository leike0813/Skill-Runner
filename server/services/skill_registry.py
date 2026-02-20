import json
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from ..config import config
from ..models import ExecutionMode, SkillManifest
from .engine_policy import apply_engine_policy_to_manifest
from .manifest_artifact_inference import infer_manifest_artifacts

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Registry for discovering and managing available skills.
    
    Capabilities:
    - Scans `skills/` directory for valid skill packages.
    - Loads definitions from `assets/runner.json`.
    - Provides lookup by ID.
    """
    def __init__(self):
        self._skills: Dict[str, SkillManifest] = {}
        self._missing_execution_modes_warned: set[str] = set()

    def scan_skills(self):
        """
        Scans the SKILLS_DIR for valid skills and updates the internal cache.
        A skill is valid if it has a `SKILL.md` file.
        """
        self._skills.clear()
        skills_dir = Path(config.SYSTEM.SKILLS_DIR)
        if not skills_dir.exists():
            return

        invalid_dirs: List[str] = []

        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            if skill_dir.name.startswith("."):
                continue
            
            # Check for SKILL.md and assets/runner.json
            skill_md = skill_dir / "SKILL.md"
            runner_json = skill_dir / "assets" / "runner.json"
            
            if not skill_md.exists() or not runner_json.exists():
                invalid_dirs.append(skill_dir.name)
                continue
                
            manifest = self._load_skill_manifest(skill_dir, runner_json)
            if manifest:
                self._skills[manifest.id] = manifest
            else:
                invalid_dirs.append(skill_dir.name)

        if invalid_dirs:
            logger.warning("Ignored invalid skill directories: %s", ", ".join(sorted(set(invalid_dirs))))

    def _load_skill_manifest(self, skill_dir: Path, runner_json_path: Path) -> Optional[SkillManifest]:
        """Loads a skill manifest from disk."""
        try:
            with open(runner_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data = infer_manifest_artifacts(data, skill_dir)
                apply_engine_policy_to_manifest(data)
                if "execution_modes" not in data:
                    data["execution_modes"] = [ExecutionMode.AUTO.value]
                    if skill_dir.name not in self._missing_execution_modes_warned:
                        logger.warning(
                            "Skill '%s' is missing runner.json.execution_modes; "
                            "defaulting to ['auto'] (deprecated, please migrate).",
                            skill_dir.name,
                        )
                        self._missing_execution_modes_warned.add(skill_dir.name)

                return SkillManifest(**data, path=skill_dir)
        except Exception:
            logger.exception("Error loading skill %s", skill_dir.name)
            return None

    def list_skills(self) -> List[SkillManifest]:
        self.scan_skills() # Rescan for simplicity in v0
        return list(self._skills.values())

    def get_skill(self, skill_id: str) -> Optional[SkillManifest]:
        self.scan_skills()
        return self._skills.get(skill_id)

skill_registry = SkillRegistry()
