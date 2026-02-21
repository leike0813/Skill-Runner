import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from server.services.skill_package_validator import SkillPackageValidator


def _build_skill_zip(
    skill_id: str = "demo-temp-skill",
    *,
    top_level: str | None = None,
    skill_name: str | None = None,
    runner_id: str | None = None,
    engines: list[str] | None = None,
    include_engines: bool = True,
    unsupported_engines: list[str] | None = None,
    include_output: bool = True,
    include_runner_artifacts: bool = True,
) -> bytes:
    top = top_level or skill_id
    name = skill_name or skill_id
    rid = runner_id or skill_id
    runner: dict[str, Any] = {
        "id": rid,
        "schemas": {
            "input": "assets/input.schema.json",
            "parameter": "assets/parameter.schema.json",
            "output": "assets/output.schema.json",
        },
    }
    if include_engines:
        runner["engines"] = ["gemini"] if engines is None else engines
    if unsupported_engines is not None:
        runner["unsupported_engines"] = unsupported_engines
    if include_runner_artifacts:
        runner["artifacts"] = [{"role": "result", "pattern": "out.txt", "required": True}]
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{top}/SKILL.md", f"---\nname: {name}\n---\n")
        zf.writestr(f"{top}/assets/runner.json", json.dumps(runner))
        zf.writestr(f"{top}/assets/input.schema.json", json.dumps({"type": "object", "properties": {}}))
        zf.writestr(f"{top}/assets/parameter.schema.json", json.dumps({"type": "object", "properties": {}}))
        if include_output:
            zf.writestr(f"{top}/assets/output.schema.json", json.dumps({"type": "object", "properties": {}}))
    return bio.getvalue()


def test_rejects_multiple_top_levels():
    validator = SkillPackageValidator()
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("a/SKILL.md", "x")
        zf.writestr("b/SKILL.md", "x")
    with pytest.raises(ValueError, match="exactly one top-level directory"):
        validator.inspect_zip_top_level_from_bytes(bio.getvalue())


def test_rejects_zip_slip_on_extract(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "bad.zip"
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("demo/../../evil.txt", "boom")
    zip_path.write_bytes(bio.getvalue())
    with pytest.raises(ValueError, match="Unsafe zip entry path"):
        validator.extract_zip_safe(zip_path, tmp_path / "out")


def test_rejects_identity_mismatch(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "skill.zip"
    zip_path.write_bytes(_build_skill_zip(skill_id="demo-temp-skill", skill_name="other-name"))
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage")
    with pytest.raises(ValueError, match="identity mismatch"):
        validator.validate_skill_dir(tmp_path / "stage" / top, top, require_version=False)


def test_accepts_valid_temp_skill(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "skill.zip"
    zip_path.write_bytes(_build_skill_zip())
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage")
    skill_id, version = validator.validate_skill_dir(
        tmp_path / "stage" / top, top, require_version=False
    )
    assert skill_id == "demo-temp-skill"
    assert version is None


def test_accepts_valid_temp_skill_without_runner_artifacts(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "skill_no_artifacts.zip"
    zip_path.write_bytes(_build_skill_zip(include_runner_artifacts=False))
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_no_artifacts")
    skill_id, version = validator.validate_skill_dir(
        tmp_path / "stage_no_artifacts" / top, top, require_version=False
    )
    assert skill_id == "demo-temp-skill"
    assert version is None


def test_accepts_missing_engines_by_defaulting_to_all_supported(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "skill_missing_engines.zip"
    zip_path.write_bytes(_build_skill_zip(include_engines=False))
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_missing_engines")
    skill_id, version = validator.validate_skill_dir(
        tmp_path / "stage_missing_engines" / top, top, require_version=False
    )
    assert skill_id == "demo-temp-skill"
    assert version is None


def test_accepts_empty_engines_by_defaulting_to_all_supported(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "skill_empty_engines.zip"
    zip_path.write_bytes(_build_skill_zip(engines=[]))
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_empty_engines")
    skill_id, version = validator.validate_skill_dir(
        tmp_path / "stage_empty_engines" / top, top, require_version=False
    )
    assert skill_id == "demo-temp-skill"
    assert version is None


def test_rejects_unknown_engine_name(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "skill_unknown_engine.zip"
    zip_path.write_bytes(_build_skill_zip(engines=["gemini", "unknown"]))
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_unknown_engine")
    with pytest.raises(ValueError, match="contains unsupported engine"):
        validator.validate_skill_dir(tmp_path / "stage_unknown_engine" / top, top, require_version=False)


def test_rejects_unknown_engine_name_in_unsupported_list(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "skill_unknown_unsupported.zip"
    zip_path.write_bytes(_build_skill_zip(unsupported_engines=["unknown"]))
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_unknown_unsupported")
    with pytest.raises(ValueError, match="contains unsupported engine"):
        validator.validate_skill_dir(tmp_path / "stage_unknown_unsupported" / top, top, require_version=False)


def test_rejects_overlap_between_engines_and_unsupported_engines(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "skill_overlap.zip"
    zip_path.write_bytes(_build_skill_zip(engines=["gemini", "codex"], unsupported_engines=["gemini"]))
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_overlap")
    with pytest.raises(ValueError, match="must not overlap"):
        validator.validate_skill_dir(tmp_path / "stage_overlap" / top, top, require_version=False)


def test_rejects_effective_empty_engine_set(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "skill_effective_empty.zip"
    zip_path.write_bytes(_build_skill_zip(include_engines=False, unsupported_engines=["codex", "gemini", "iflow"]))
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_effective_empty")
    with pytest.raises(ValueError, match="resolves to no supported engines"):
        validator.validate_skill_dir(tmp_path / "stage_effective_empty" / top, top, require_version=False)
