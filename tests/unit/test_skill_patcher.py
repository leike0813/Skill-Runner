from pathlib import Path

import pytest

from server.models import ManifestArtifact
from server.services.skill_patcher import SkillPatcher


def test_generate_patch_content_auto_mode_forbids_questions_and_has_artifact_redirect():
    patcher = SkillPatcher()
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]
    content = patcher.generate_patch_content(artifacts, execution_mode="auto")
    assert "# Runtime Output Overrides" in content
    assert "{{ run_dir }}/artifacts/final.md" in content
    assert "## Runtime Completion Contract (Injected by Skill Runner)" in content
    assert "__SKILL_DONE__" in content
    assert "must NOT ask the user" in content


def test_generate_patch_content_interactive_mode_keeps_ask_user_optional():
    patcher = SkillPatcher()
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]
    content = patcher.generate_patch_content(artifacts, execution_mode="interactive")
    assert "# Runtime Output Overrides" in content
    assert "{{ run_dir }}/artifacts/final.md" in content
    assert "must NOT ask the user" not in content
    assert "structured ask_user payload" not in content
    assert "<ASK_USER_YAML>" in content
    assert "use YAML (NOT JSON)" in content
    assert "optional UI hints only" in content
    assert "MUST NOT emit any __SKILL_DONE__ marker" in content


def test_patch_skill_md_is_idempotent(tmp_path: Path):
    patcher = SkillPatcher()
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Demo\n\nhello\n", encoding="utf-8")
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]

    patcher.patch_skill_md(skill_dir, artifacts, execution_mode="interactive")
    once_content = skill_md.read_text(encoding="utf-8")
    patcher.patch_skill_md(skill_dir, artifacts, execution_mode="interactive")
    twice_content = skill_md.read_text(encoding="utf-8")

    assert once_content == twice_content
    assert once_content.count("## Runtime Completion Contract (Injected by Skill Runner)") == 1
    assert once_content.count("# Runtime Output Overrides") == 1
    assert once_content.count("# Automation Context") == 1


def test_patch_skill_md_missing_completion_contract_markdown_fails_fast(tmp_path: Path):
    patcher = SkillPatcher()
    patcher._completion_contract_path = tmp_path / "missing-completion-contract.md"
    skill_dir = tmp_path / "demo-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]

    with pytest.raises(RuntimeError, match="completion contract markdown is missing"):
        patcher.patch_skill_md(skill_dir, artifacts, execution_mode="auto")
