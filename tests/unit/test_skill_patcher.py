from server.models import ManifestArtifact
from server.services.skill_patcher import SkillPatcher


def test_generate_patch_content_auto_mode_forbids_questions_and_has_artifact_redirect():
    patcher = SkillPatcher()
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]
    content = patcher.generate_patch_content(artifacts, execution_mode="auto")
    assert "# Runtime Output Overrides" in content
    assert "{{ run_dir }}/artifacts/final.md" in content
    assert "must NOT ask the user" in content


def test_generate_patch_content_interactive_mode_allows_structured_ask_user():
    patcher = SkillPatcher()
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]
    content = patcher.generate_patch_content(artifacts, execution_mode="interactive")
    assert "# Runtime Output Overrides" in content
    assert "{{ run_dir }}/artifacts/final.md" in content
    assert "must NOT ask the user" not in content
    assert "structured ask_user payload" in content
    assert "interaction_id, kind, prompt" in content
    assert "choose_one, confirm, fill_fields, open_text, risk_ack" in content
    assert "options, ui_hints, default_decision_policy" in content
