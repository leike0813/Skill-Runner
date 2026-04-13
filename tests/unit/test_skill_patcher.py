from pathlib import Path
from unittest.mock import patch

import pytest

from server.models import ManifestArtifact
from server.services.skill import skill_patcher as patcher_module
from server.services.skill.skill_patcher import SkillPatcher


def _sample_output_schema_markdown() -> str:
    return (
        "### Output Schema Specification\n\n"
        "Run-scoped machine schema artifact: `.audit/contracts/target_output_schema.json`.\n\n"
        "| Field | Type | Required | Description |\n"
        "|-------|------|----------|-------------|\n"
        "| `__SKILL_DONE__` | boolean (`true`) | ✅ | Completion signal. |\n"
        "| `value` | string | ✅ | result value |\n"
    )


def test_generate_patch_content_auto_mode_forbids_questions_and_has_artifact_redirect():
    patcher = SkillPatcher()
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]
    content = patcher.generate_patch_content(
        artifacts,
        execution_mode="auto",
        output_schema_summary_markdown=_sample_output_schema_markdown(),
    )
    assert "Runtime Enforcement (Injected by Skill Runner" in content
    assert "# Runtime Output Overrides" in content
    assert "Prefer writing those final deliverables under `<cwd>/artifacts/`" in content
    assert "nested folders allowed" in content
    assert "## Output Format Contract" in content
    assert "### Output Schema Specification" in content
    assert "__SKILL_DONE__" in content
    assert ".audit/contracts/target_output_schema.json" in content
    assert "Execution Mode: AUTO (Non-Interactive)" in content
    assert "MUST NOT ask the user" in content


def test_generate_patch_content_interactive_mode_uses_json_union_contract():
    patcher = SkillPatcher()
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]
    content = patcher.generate_patch_content(artifacts, execution_mode="interactive")
    assert "# Runtime Output Overrides" in content
    assert "Prefer writing those final deliverables under `<cwd>/artifacts/`" in content
    assert "Execution Mode: INTERACTIVE" in content
    assert "<ASK_USER_YAML>" in content
    assert "Legacy `<ASK_USER_YAML>` is not a valid output protocol" in content
    assert "__SKILL_DONE__ = false" in content
    assert "message" in content
    assert "ui_hints" in content
    assert "Do not wrap the JSON in Markdown fences." in content
    assert "MUST NOT ask the user" not in content


def test_patch_skill_md_is_idempotent(tmp_path: Path):
    patcher = SkillPatcher()
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Demo\n\nhello\n", encoding="utf-8")
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]

    patcher.patch_skill_md(
        skill_dir,
        artifacts,
        execution_mode="interactive",
        output_schema_summary_markdown=_sample_output_schema_markdown(),
    )
    once_content = skill_md.read_text(encoding="utf-8")
    patcher.patch_skill_md(
        skill_dir,
        artifacts,
        execution_mode="interactive",
        output_schema_summary_markdown=_sample_output_schema_markdown(),
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

    patcher.patch_skill_md(
        skill_dir,
        [],
        execution_mode="auto",
        output_schema_summary_markdown=None,
    )
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
