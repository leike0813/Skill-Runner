import json
import yaml # type: ignore
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from ..config import config
from ..models import SkillManifest

class SkillRegistry:
    """
    Registry for discovering and managing available skills.
    
    Capabilities:
    - Scans `skills/` directory for valid skill packages.
    - Loads definitions from `assets/runner.json` or infers from directory structure.
    - Provides lookup by ID.
    """
    def __init__(self):
        self._skills: Dict[str, SkillManifest] = {}

    def scan_skills(self):
        """
        Scans the SKILLS_DIR for valid skills and updates the internal cache.
        A skill is valid if it has a `SKILL.md` file.
        """
        self._skills.clear()
        skills_dir = Path(config.SYSTEM.SKILLS_DIR)
        if not skills_dir.exists():
            return

        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            
            # Check for SKILL.md and assets/runner.json
            skill_md = skill_dir / "SKILL.md"
            runner_json = skill_dir / "assets" / "runner.json"
            
            if not skill_md.exists():
                continue
                
            manifest = self._load_skill_manifest(skill_dir, runner_json)
            if manifest:
                self._skills[manifest.id] = manifest

    def _load_skill_manifest(self, skill_dir: Path, runner_json_path: Path) -> Optional[SkillManifest]:
        """Loads a skill manifest from disk."""
        try:
            if runner_json_path.exists():
                with open(runner_json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # If artifacts are NOT explicitly defined, try to scan them from output schema
                    if ("artifacts" not in data or not data["artifacts"]) and "schemas" in data and "output" in data["schemas"]:
                         output_schema_path = skill_dir / data["schemas"]["output"]
                         data["artifacts"] = self._scan_artifacts(output_schema_path)

                    return SkillManifest(**data, path=skill_dir)
            
            # Fallback
            return SkillManifest(
                id=skill_dir.name,
                name=skill_dir.name,
                description="Loaded from directory",
                engines=["codex"],
                path=skill_dir
            )
        except Exception as e:
            logger.exception("Error loading skill %s", skill_dir.name)
            return None

    def _scan_artifacts(self, schema_path: Path) -> List[Dict[str, Any]]:
        """
        Scans output.schema.json for properties marked with x-type: artifact.
        Returns list of dicts compatible with ManifestArtifact.
        """
        artifacts: List[Dict[str, Any]] = []
        if not schema_path.exists():
            return artifacts
            
        try:
            with open(schema_path, "r") as f:
                schema = json.load(f)
                
            props = schema.get("properties", {})
            required_keys = set(schema.get("required", []))
            for key, val in props.items():
                x_type = val.get("x-type")
                if x_type in ["artifact", "file"]:
                    # Create artifact definition
                    # Prefer x-filename for pattern, fallback to key
                    pattern = val.get("x-filename", key)
                    role = val.get("x-role", "output")
                    
                    artifacts.append({
                        "role": role, 
                        "pattern": pattern,
                        "required": key in required_keys
                    })
        except Exception as e:
            logger.exception("Error scanning artifacts")
            pass
            
        return artifacts

    def list_skills(self) -> List[SkillManifest]:
        self.scan_skills() # Rescan for simplicity in v0
        return list(self._skills.values())

    def get_skill(self, skill_id: str) -> Optional[SkillManifest]:
        self.scan_skills()
        return self._skills.get(skill_id)

skill_registry = SkillRegistry()

logger = logging.getLogger(__name__)
