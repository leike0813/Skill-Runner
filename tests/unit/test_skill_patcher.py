from pathlib import Path
from unittest.mock import patch

import pytest

from server.models import ManifestArtifact
from server.services.skill import skill_patcher as patcher_module
from server.services.skill.skill_patcher import SkillPatcher

def _expected_skill_run_feedback_patch(feedback_path: str) -> str:
    return f"""## Skill Run Feedback Sidecar

After the original skill task has completed successfully, write a short Markdown feedback note to:

`{feedback_path}`

Do not create this file when the task fails, is canceled, or is still waiting for user input. Do not add this file to `result.json` or to any output schema.

The note is free-form Markdown for future skill maintenance. Focus on issues encountered during this run, ambiguous instructions, missing context, fragile steps, tooling problems, and concrete suggestions for improving the skill."""


def _sample_output_schema_markdown() -> str:
    return (
        "### Output Contract Details\n\n"
        "Run-scoped machine schema artifact: `.audit/contracts/target_output_schema.json`.\n\n"
        "| Field | Type | Required | Description |\n"
        "|-------|------|----------|-------------|\n"
        "| `__SKILL_DONE__` | boolean (`true`) | ✅ | Completion signal. |\n"
        "| `value` | string | ✅ | result value |\n"
    )


def test_generate_patch_content_auto_mode_forbids_questions_and_has_artifact_redirect():
    patcher = SkillPatcher()
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]
    run_dir = Path("/tmp/demo-run")
    content = patcher.generate_patch_content(
        artifacts,
        run_dir=run_dir,
        execution_mode="auto",
        output_contract_details_markdown=_sample_output_schema_markdown(),
    )
    assert "Runtime Enforcement (Injected by Skill Runner" in content
    assert "# Runtime Output Overrides" in content
    assert "Prefer writing those final deliverables under `<cwd>/artifacts/`" in content
    assert f"`{run_dir.as_posix()}/artifacts/`" in content
    assert "nested folders allowed" in content
    assert "## Output Format Contract" in content
    assert "### Output Contract Details" in content
    assert "__SKILL_DONE__" in content
    assert ".audit/contracts/target_output_schema.json" in content
    assert "Execution Mode: AUTO (Non-Interactive)" in content
    assert "ask the user for clarification, confirmation, or any form of decision" in content


def test_generate_patch_content_interactive_mode_uses_json_union_contract():
    patcher = SkillPatcher()
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]
    run_dir = Path("/tmp/demo-run")
    content = patcher.generate_patch_content(
        artifacts,
        run_dir=run_dir,
        execution_mode="interactive",
        output_contract_details_markdown=_sample_output_schema_markdown(),
    )
    assert "# Runtime Output Overrides" in content
    assert "Prefer writing those final deliverables under `<cwd>/artifacts/`" in content
    assert f"`{run_dir.as_posix()}/artifacts/`" in content
    assert "Execution Mode: INTERACTIVE" in content
    assert "Beyond these cases, strive to execute tasks autonomously to the greatest extent possible." in content
    assert "Do not mix the final and pending branches in the same turn." in content
    assert "Supported `ui_hints.kind` values" not in content
    assert "Pending branch example" not in content
    assert "### Output Contract Details" in content
    assert "#### Pending Branch Contract" not in content
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
        run_dir=tmp_path / "run",
        execution_mode="interactive",
        output_contract_details_markdown=_sample_output_schema_markdown(),
    )
    once_content = skill_md.read_text(encoding="utf-8")
    patcher.patch_skill_md(
        skill_dir,
        artifacts,
        run_dir=tmp_path / "run",
        execution_mode="interactive",
        output_contract_details_markdown=_sample_output_schema_markdown(),
    )
    twice_content = skill_md.read_text(encoding="utf-8")

    assert once_content == twice_content
    assert once_content.count("Runtime Enforcement (Injected by Skill Runner") == 1
    assert once_content.count("# Runtime Output Overrides") == 1
    assert once_content.count("## Output Format Contract") == 1
    assert once_content.count("### Output Contract Details") == 1
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
        run_dir=tmp_path / "run",
        execution_mode="auto",
        output_contract_details_markdown=None,
    )
    content = skill_md.read_text(encoding="utf-8")
    assert "## Output Format Contract" in content
    assert "### Output Contract Details" not in content


def test_generate_patch_content_feedback_text_exact_and_last():
    patcher = SkillPatcher()
    feedback_path = "/tmp/demo-run/result/demo-skill.2/_skill_run_feedback.md"
    content = patcher.generate_patch_content(
        [],
        run_dir=Path("/tmp/demo-run"),
        execution_mode="interactive",
        collect_skill_run_feedback=True,
        feedback_path=feedback_path,
    )
    assert content.rstrip().endswith(_expected_skill_run_feedback_patch(feedback_path))


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
