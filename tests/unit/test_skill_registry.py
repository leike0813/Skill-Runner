import json

from server.config import config
from server.services.skill_registry import SkillRegistry


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
                "x-filename": "text.md",
            },
            "info_path": {
                "type": "string",
                "x-type": "file",
            },
            "meta": {"type": "object"},
        },
        "required": ["text_path"],
    }
    (assets_dir / "output.schema.json").write_text(json.dumps(output_schema))
    runner = {
        "id": "demo-skill",
        "schemas": {"output": "assets/output.schema.json"},
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


def test_scan_skips_excluded_and_invalid_dirs(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    invalid_dir = skills_dir / "broken-skill"
    invalid_dir.mkdir()
    (invalid_dir / "SKILL.md").write_text("# Broken")

    valid_dir = skills_dir / "valid-skill"
    valid_assets = valid_dir / "assets"
    valid_assets.mkdir(parents=True)
    (valid_dir / "SKILL.md").write_text("# Valid")
    (valid_assets / "runner.json").write_text(
        json.dumps(
            {
                "id": "valid-skill",
                "version": "1.0.0",
                "engines": ["gemini"],
                "schemas": {
                    "input": "assets/input.schema.json",
                    "parameter": "assets/parameter.schema.json",
                    "output": "assets/output.schema.json",
                },
                "artifacts": [],
            }
        )
    )
    (valid_assets / "input.schema.json").write_text(json.dumps({"type": "object"}))
    (valid_assets / "parameter.schema.json").write_text(json.dumps({"type": "object"}))
    (valid_assets / "output.schema.json").write_text(json.dumps({"type": "object"}))

    old_skills_dir = config.SYSTEM.SKILLS_DIR
    config.defrost()
    config.SYSTEM.SKILLS_DIR = str(skills_dir)
    config.freeze()

    try:
        registry = SkillRegistry()
        skills = registry.list_skills()
        ids = {skill.id for skill in skills}
        assert "valid-skill" in ids
        assert "broken-skill" not in ids
    finally:
        config.defrost()
        config.SYSTEM.SKILLS_DIR = old_skills_dir
        config.freeze()


def test_scan_missing_execution_modes_falls_back_to_auto(tmp_path, caplog):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skill_dir = skills_dir / "legacy-skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Legacy")
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": "legacy-skill",
                "engines": ["gemini"],
                "schemas": {"output": "assets/output.schema.json"},
            }
        )
    )
    (assets_dir / "output.schema.json").write_text(json.dumps({"type": "object"}))

    old_skills_dir = config.SYSTEM.SKILLS_DIR
    config.defrost()
    config.SYSTEM.SKILLS_DIR = str(skills_dir)
    config.freeze()

    try:
        registry = SkillRegistry()
        caplog.set_level("WARNING")
        registry.scan_skills()
        skill = registry.get_skill("legacy-skill")
        assert skill is not None
        assert [mode.value for mode in skill.execution_modes] == ["auto"]
        assert "missing runner.json.execution_modes" in caplog.text
    finally:
        config.defrost()
        config.SYSTEM.SKILLS_DIR = old_skills_dir
        config.freeze()
