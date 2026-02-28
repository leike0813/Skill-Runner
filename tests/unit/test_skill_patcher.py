from pathlib import Path
from unittest.mock import patch

import pytest

from server.models import ManifestArtifact
from server.services.skill import skill_patcher as patcher_module
from server.services.skill.skill_patcher import SkillPatcher


def _sample_output_schema() -> dict:
    return {
        "type": "object",
        "required": ["value"],
        "properties": {
            "value": {"type": "string", "description": "result value"},
        },
        "additionalProperties": False,
    }


def test_generate_patch_content_auto_mode_forbids_questions_and_has_artifact_redirect():
    patcher = SkillPatcher()
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]
    content = patcher.generate_patch_content(
        artifacts,
        execution_mode="auto",
        output_schema=_sample_output_schema(),
    )
    assert "Runtime Enforcement (Injected by Skill Runner" in content
    assert "# Runtime Output Overrides" in content
    assert "{{ run_dir }}/artifacts/final.md" in content
    assert "## Output Format Contract" in content
    assert "### Output Schema Specification" in content
    assert "__SKILL_DONE__" in content
    assert "Execution Mode: AUTO (Non-Interactive)" in content
    assert "MUST NOT ask the user" in content


def test_generate_patch_content_interactive_mode_keeps_ask_user_optional():
    patcher = SkillPatcher()
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]
    content = patcher.generate_patch_content(artifacts, execution_mode="interactive")
    assert "# Runtime Output Overrides" in content
    assert "{{ run_dir }}/artifacts/final.md" in content
    assert "Execution Mode: INTERACTIVE" in content
    assert "<ASK_USER_YAML>" in content
    assert "MUST NOT ask the user" not in content


def test_patch_skill_md_is_idempotent(tmp_path: Path):
    patcher = SkillPatcher()
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Demo\n\nhello\n", encoding="utf-8")
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]
    output_schema = _sample_output_schema()

    patcher.patch_skill_md(
        skill_dir,
        artifacts,
        execution_mode="interactive",
        output_schema=output_schema,
    )
    once_content = skill_md.read_text(encoding="utf-8")
    patcher.patch_skill_md(
        skill_dir,
        artifacts,
        execution_mode="interactive",
        output_schema=output_schema,
    )
    twice_content = skill_md.read_text(encoding="utf-8")

    assert once_content == twice_content
    assert once_content.count("Runtime Enforcement (Injected by Skill Runner") == 1
    assert once_content.count("# Runtime Output Overrides") == 1
    assert once_content.count("## Output Format Contract") == 1
    assert once_content.count("### Output Schema Specification") == 1
    assert once_content.count("## Execution Mode: INTERACTIVE") == 1


def test_patch_skill_md_without_output_schema_skips_dynamic_schema_section(tmp_path: Path):
    patcher = SkillPatcher()
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Demo\n", encoding="utf-8")

    patcher.patch_skill_md(skill_dir, [], execution_mode="auto", output_schema=None)
    content = skill_md.read_text(encoding="utf-8")
    assert "## Output Format Contract" in content
    assert "### Output Schema Specification" not in content


def test_patch_skill_md_missing_template_fails_fast(tmp_path: Path):
    patcher = SkillPatcher()
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]

    with patch.object(
        patcher_module,
        "load_template_content",
        side_effect=RuntimeError("Skill patch template is missing"),
    ):
        with pytest.raises(RuntimeError, match="Skill patch template is missing"):
            patcher.patch_skill_md(skill_dir, artifacts, execution_mode="auto")
