from pathlib import Path
from unittest.mock import patch

import pytest

from server.models import ManifestArtifact
from server.services.skill import skill_patcher as patcher_module
from server.services.skill.skill_patch_output_schema import OUTPUT_CONTRACT_DETAILS_MARKER
from server.services.skill.skill_patcher import (
    MODE_AUTO_PATCH_MARKER,
    MODE_INTERACTIVE_PATCH_MARKER,
    OUTPUT_FORMAT_CONTRACT_MARKER,
    RUNTIME_ENFORCEMENT_MARKER,
    ARTIFACT_PATCH_MARKER,
    SkillPatcher,
)


def _output_contract_details_markdown() -> str:
    return (
        "### Output Contract Details\n\n"
        "| Field | Type | Required | Description |\n"
        "|-------|------|----------|-------------|\n"
        "| `__SKILL_DONE__` | boolean (`true`) | ✅ | Completion signal. |\n"
        "| `value` | string | ✅ | result value |\n"
    )


def test_build_patch_plan_fixed_only_auto_mode():
    patcher = SkillPatcher()
    plan = patcher.build_patch_plan(
        artifacts=[],
        run_dir=Path("/tmp/demo-run"),
        execution_mode="auto",
        output_contract_details_markdown=None,
    )
    markers = [item.marker for item in plan]
    assert markers == [
        RUNTIME_ENFORCEMENT_MARKER,
        OUTPUT_FORMAT_CONTRACT_MARKER,
        MODE_AUTO_PATCH_MARKER,
    ]


def test_build_patch_plan_with_artifact_patch():
    patcher = SkillPatcher()
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]
    plan = patcher.build_patch_plan(
        artifacts=artifacts,
        run_dir=Path("/tmp/demo-run"),
        execution_mode="auto",
        output_contract_details_markdown=None,
    )
    markers = [item.marker for item in plan]
    assert markers == [
        RUNTIME_ENFORCEMENT_MARKER,
        ARTIFACT_PATCH_MARKER,
        OUTPUT_FORMAT_CONTRACT_MARKER,
        MODE_AUTO_PATCH_MARKER,
    ]
    assert "`/tmp/demo-run/artifacts/`" in plan[1].content


def test_build_patch_plan_with_output_schema_and_interactive_mode():
    patcher = SkillPatcher()
    plan = patcher.build_patch_plan(
        artifacts=[],
        run_dir=Path("/tmp/demo-run"),
        execution_mode="interactive",
        output_contract_details_markdown=_output_contract_details_markdown(),
    )
    markers = [item.marker for item in plan]
    assert markers == [
        RUNTIME_ENFORCEMENT_MARKER,
        OUTPUT_FORMAT_CONTRACT_MARKER,
        OUTPUT_CONTRACT_DETAILS_MARKER,
        MODE_INTERACTIVE_PATCH_MARKER,
    ]


def test_patch_plan_order_is_stable_for_all_modules():
    patcher = SkillPatcher()
    artifacts = [ManifestArtifact(role="result", pattern="out.json")]
    plan = patcher.build_patch_plan(
        artifacts=artifacts,
        run_dir=Path("/tmp/demo-run"),
        execution_mode="interactive",
        output_contract_details_markdown=_output_contract_details_markdown(),
    )
    markers = [item.marker for item in plan]
    assert markers == [
        RUNTIME_ENFORCEMENT_MARKER,
        ARTIFACT_PATCH_MARKER,
        OUTPUT_FORMAT_CONTRACT_MARKER,
        OUTPUT_CONTRACT_DETAILS_MARKER,
        MODE_INTERACTIVE_PATCH_MARKER,
    ]


def test_patch_skill_md_is_idempotent_with_pipeline(tmp_path: Path):
    patcher = SkillPatcher()
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("# Skill\n", encoding="utf-8")
    artifacts = [ManifestArtifact(role="report", pattern="final.md")]

    changed_1 = patcher.patch_skill_md(
        skill_dir=skill_dir,
        artifacts=artifacts,
        run_dir=tmp_path / "run",
        execution_mode="interactive",
        output_contract_details_markdown=_output_contract_details_markdown(),
    )
    content_once = skill_md.read_text(encoding="utf-8")
    changed_2 = patcher.patch_skill_md(
        skill_dir=skill_dir,
        artifacts=artifacts,
        run_dir=tmp_path / "run",
        execution_mode="interactive",
        output_contract_details_markdown=_output_contract_details_markdown(),
    )
    content_twice = skill_md.read_text(encoding="utf-8")
    assert changed_1 is True
    assert changed_2 is False
    assert content_once == content_twice


def test_build_patch_plan_missing_template_fails_fast():
    patcher = SkillPatcher()
    with patch.object(
        patcher_module,
        "load_template_content",
        side_effect=RuntimeError("Skill patch template is missing"),
    ):
        with pytest.raises(RuntimeError, match="Skill patch template is missing"):
            patcher.build_patch_plan(
                artifacts=[],
                run_dir=Path("/tmp/demo-run"),
                execution_mode="auto",
                output_contract_details_markdown=None,
            )
