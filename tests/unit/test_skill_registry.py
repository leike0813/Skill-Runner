import json
from pathlib import Path
import pytest

from server.services.skill_registry import SkillRegistry
from server.config import config


def test_scan_artifacts_from_output_schema(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skill_dir = skills_dir / "demo-skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)

    (skill_dir / "SKILL.md").write_text("# Skill")
    output_schema = {
        "type": "object",
        "properties": {
            "text_path": {
                "type": "string",
                "x-type": "artifact",
                "x-role": "text",
                "x-filename": "text.md"
            },
            "info_path": {
                "type": "string",
                "x-type": "file"
            },
            "meta": {"type": "object"}
        },
        "required": ["text_path"]
    }
    (assets_dir / "output.schema.json").write_text(json.dumps(output_schema))
    runner = {
        "id": "demo-skill",
        "schemas": {"output": "assets/output.schema.json"}
    }
    (assets_dir / "runner.json").write_text(json.dumps(runner))

    old_skills_dir = config.SYSTEM.SKILLS_DIR
    config.defrost()
    config.SYSTEM.SKILLS_DIR = str(skills_dir)
    config.freeze()
    try:
        registry = SkillRegistry()
        registry.scan_skills()
        skill = registry.get_skill("demo-skill")
        assert skill is not None
        assert len(skill.artifacts) == 2

        artifacts = {a.role: a for a in skill.artifacts}
        assert artifacts["text"].pattern == "text.md"
        assert artifacts["text"].required is True
        assert artifacts["output"].pattern == "info_path"
        assert artifacts["output"].required is False
    finally:
        config.defrost()
        config.SYSTEM.SKILLS_DIR = old_skills_dir
        config.freeze()
