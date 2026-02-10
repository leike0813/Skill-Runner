import io
import json
import zipfile
from pathlib import Path

import pytest

from server.services.skill_package_validator import SkillPackageValidator


def _build_skill_zip(
    skill_id: str = "demo-temp-skill",
    *,
    top_level: str | None = None,
    skill_name: str | None = None,
    runner_id: str | None = None,
    include_output: bool = True,
) -> bytes:
    top = top_level or skill_id
    name = skill_name or skill_id
    rid = runner_id or skill_id
    runner = {
        "id": rid,
        "engines": ["gemini"],
        "schemas": {
            "input": "assets/input.schema.json",
            "parameter": "assets/parameter.schema.json",
            "output": "assets/output.schema.json",
        },
        "artifacts": [{"role": "result", "pattern": "out.txt", "required": True}],
    }
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
