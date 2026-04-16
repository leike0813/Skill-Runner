import json
from contextlib import contextmanager
from pathlib import Path

from server.config import config
from server.services.skill.skill_registry import SkillRegistry


@contextmanager
def _skill_dirs(user_dir: Path, *, builtin_dir: Path | None = None):
    old_user_dir = config.SYSTEM.SKILLS_DIR
    old_builtin_dir = config.SYSTEM.SKILLS_BUILTIN_DIR
    effective_builtin = builtin_dir or (user_dir.parent / "skills_builtin_empty")
    effective_builtin.mkdir(parents=True, exist_ok=True)
    config.defrost()
    config.SYSTEM.SKILLS_DIR = str(user_dir)
    config.SYSTEM.SKILLS_BUILTIN_DIR = str(effective_builtin)
    config.freeze()
    try:
        yield
    finally:
        config.defrost()
        config.SYSTEM.SKILLS_DIR = old_user_dir
        config.SYSTEM.SKILLS_BUILTIN_DIR = old_builtin_dir
        config.freeze()


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

    with _skill_dirs(skills_dir):
        registry = SkillRegistry()
        registry.scan_skills()
        skill = registry.get_skill("demo-skill")
        assert skill is not None
        assert len(skill.artifacts) == 2

        artifacts = {a.role: a for a in skill.artifacts}
        assert artifacts["text"].pattern == "text_path"
        assert artifacts["text"].required is True
        assert artifacts["output"].pattern == "info_path"
        assert artifacts["output"].required is False


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

    with _skill_dirs(skills_dir):
        registry = SkillRegistry()
        skills = registry.list_skills()
        ids = {skill.id for skill in skills}
        assert "valid-skill" in ids
        assert "broken-skill" not in ids


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

    with _skill_dirs(skills_dir):
        registry = SkillRegistry()
        caplog.set_level("WARNING")
        registry.scan_skills()
        skill = registry.get_skill("legacy-skill")
        assert skill is not None
        assert [mode.value for mode in skill.execution_modes] == ["auto"]
        assert "missing runner.json.execution_modes" in caplog.text


def test_scan_missing_engines_defaults_to_all_supported(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skill_dir = skills_dir / "legacy-engine-skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Legacy Engine")
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": "legacy-engine-skill",
                "execution_modes": ["auto"],
                "schemas": {"output": "assets/output.schema.json"},
            }
        )
    )
    (assets_dir / "output.schema.json").write_text(json.dumps({"type": "object"}))

    with _skill_dirs(skills_dir):
        registry = SkillRegistry()
        registry.scan_skills()
        skill = registry.get_skill("legacy-engine-skill")
        assert skill is not None
        assert skill.effective_engines == ["codex", "gemini", "opencode", "claude", "qwen"]
        assert skill.engines == []


def test_scan_loads_manifest_max_attempt(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skill_dir = skills_dir / "interactive-max-attempt-skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Interactive Max Attempt")
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": "interactive-max-attempt-skill",
                "engines": ["codex"],
                "execution_modes": ["interactive"],
                "max_attempt": 7,
                "schemas": {"output": "assets/output.schema.json"},
            }
        )
    )
    (assets_dir / "output.schema.json").write_text(json.dumps({"type": "object"}))

    with _skill_dirs(skills_dir):
        registry = SkillRegistry()
        registry.scan_skills()
        skill = registry.get_skill("interactive-max-attempt-skill")
        assert skill is not None
        assert skill.max_attempt == 7


def test_scan_skills_falls_back_to_builtin_when_user_dir_empty(tmp_path):
    user_dir = tmp_path / "skills"
    user_dir.mkdir()
    builtin_dir = tmp_path / "skills_builtin"
    skill_dir = builtin_dir / "builtin-only-skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Builtin only")
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": "builtin-only-skill",
                "version": "1.0.0",
                "engines": ["gemini"],
                "execution_modes": ["auto"],
                "schemas": {"output": "assets/output.schema.json"},
            }
        )
    )
    (assets_dir / "output.schema.json").write_text(json.dumps({"type": "object"}))

    with _skill_dirs(user_dir, builtin_dir=builtin_dir):
        registry = SkillRegistry()
        skill = registry.get_skill("builtin-only-skill")
        assert skill is not None
        assert skill.path == skill_dir


def test_scan_skills_user_overrides_builtin_on_same_skill_id(tmp_path):
    user_dir = tmp_path / "skills"
    builtin_dir = tmp_path / "skills_builtin"
    user_skill_dir = user_dir / "duplicate-skill"
    builtin_skill_dir = builtin_dir / "duplicate-skill"
    (user_skill_dir / "assets").mkdir(parents=True, exist_ok=True)
    (builtin_skill_dir / "assets").mkdir(parents=True, exist_ok=True)
    (user_skill_dir / "SKILL.md").write_text("# User")
    (builtin_skill_dir / "SKILL.md").write_text("# Builtin")
    (user_skill_dir / "assets" / "runner.json").write_text(
        json.dumps(
            {
                "id": "duplicate-skill",
                "version": "2.0.0",
                "engines": ["codex"],
                "execution_modes": ["auto"],
                "schemas": {"output": "assets/output.schema.json"},
            }
        )
    )
    (builtin_skill_dir / "assets" / "runner.json").write_text(
        json.dumps(
            {
                "id": "duplicate-skill",
                "version": "1.0.0",
                "engines": ["gemini"],
                "execution_modes": ["auto"],
                "schemas": {"output": "assets/output.schema.json"},
            }
        )
    )
    (user_skill_dir / "assets" / "output.schema.json").write_text(json.dumps({"type": "object"}))
    (builtin_skill_dir / "assets" / "output.schema.json").write_text(json.dumps({"type": "object"}))

    with _skill_dirs(user_dir, builtin_dir=builtin_dir):
        registry = SkillRegistry()
        skill = registry.get_skill("duplicate-skill")
        assert skill is not None
        assert skill.version == "2.0.0"
        assert skill.path == user_skill_dir
