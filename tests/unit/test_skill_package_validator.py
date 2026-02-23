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
    include_engines: bool = True,
    unsupported_engines: list[str] | None = None,
    legacy_unsupport_engine: list[str] | None = None,
    include_output: bool = True,
    include_runner_artifacts: bool = True,
    include_execution_modes: bool = True,
    max_attempt: Any = None,
    input_schema_override: dict[str, Any] | None = None,
    parameter_schema_override: dict[str, Any] | None = None,
    output_schema_override: dict[str, Any] | None = None,
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
        runner["engines"] = ["gemini"]
    if unsupported_engines is not None:
        runner["unsupported_engines"] = unsupported_engines
    if legacy_unsupport_engine is not None:
        runner["unsupport_engine"] = legacy_unsupport_engine
    if include_runner_artifacts:
        runner["artifacts"] = [{"role": "result", "pattern": "out.txt", "required": True}]
    if include_execution_modes:
        runner["execution_modes"] = ["auto", "interactive"]
    if max_attempt is not None:
        runner["max_attempt"] = max_attempt
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{top}/SKILL.md", f"---\nname: {name}\n---\n")
        zf.writestr(f"{top}/assets/runner.json", json.dumps(runner))
        zf.writestr(
            f"{top}/assets/input.schema.json",
            json.dumps(input_schema_override or {"type": "object", "properties": {}}),
        )
        zf.writestr(
            f"{top}/assets/parameter.schema.json",
            json.dumps(parameter_schema_override or {"type": "object", "properties": {}}),
        )
        if include_output:
            zf.writestr(
                f"{top}/assets/output.schema.json",
                json.dumps(output_schema_override or {"type": "object", "properties": {}}),
            )
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


def test_accepts_valid_temp_skill_without_engines(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "skill_no_engines.zip"
    zip_path.write_bytes(_build_skill_zip(include_engines=False))
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_no_engines")
    skill_id, version = validator.validate_skill_dir(
        tmp_path / "stage_no_engines" / top, top, require_version=False
    )
    assert skill_id == "demo-temp-skill"
    assert version is None


def test_rejects_missing_execution_modes(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "missing_modes.zip"
    zip_path.write_bytes(_build_skill_zip(include_execution_modes=False))
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_missing_modes")
    with pytest.raises(ValueError, match="execution_modes"):
        validator.validate_skill_dir(
            tmp_path / "stage_missing_modes" / top,
            top,
            require_version=False,
        )


def test_rejects_overlapping_engines_and_unsupported_engines(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "overlap_engines.zip"
    zip_path.write_bytes(
        _build_skill_zip(unsupported_engines=["gemini"])
    )
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_overlap_engines")
    with pytest.raises(ValueError, match="must not overlap"):
        validator.validate_skill_dir(
            tmp_path / "stage_overlap_engines" / top,
            top,
            require_version=False,
        )


def test_rejects_empty_effective_engines_when_engines_omitted(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "empty_effective_engines.zip"
    zip_path.write_bytes(
        _build_skill_zip(
            include_engines=False,
            unsupported_engines=["codex", "gemini", "iflow"],
        )
    )
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_empty_effective_engines")
    with pytest.raises(ValueError, match="must not be empty"):
        validator.validate_skill_dir(
            tmp_path / "stage_empty_effective_engines" / top,
            top,
            require_version=False,
        )


def test_rejects_legacy_unsupport_engine_field(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "legacy_unsupport_engine.zip"
    zip_path.write_bytes(
        _build_skill_zip(legacy_unsupport_engine=["gemini"])
    )
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_legacy_unsupport_engine")
    with pytest.raises(ValueError, match="renamed to 'unsupported_engines'"):
        validator.validate_skill_dir(
            tmp_path / "stage_legacy_unsupport_engine" / top,
            top,
            require_version=False,
        )


def test_rejects_invalid_input_schema_extension_key(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "invalid_input_schema.zip"
    zip_path.write_bytes(
        _build_skill_zip(
            input_schema_override={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "x-input-source": "bad-source"}
                },
            }
        )
    )
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_invalid_input_schema")
    with pytest.raises(ValueError, match="Invalid input schema"):
        validator.validate_skill_dir(
            tmp_path / "stage_invalid_input_schema" / top,
            top,
            require_version=False,
        )


def test_rejects_invalid_parameter_schema_shape(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "invalid_parameter_schema.zip"
    zip_path.write_bytes(
        _build_skill_zip(
            parameter_schema_override={"type": "array"},
        )
    )
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_invalid_parameter_schema")
    with pytest.raises(ValueError, match="Invalid parameter schema"):
        validator.validate_skill_dir(
            tmp_path / "stage_invalid_parameter_schema" / top,
            top,
            require_version=False,
        )


def test_rejects_invalid_output_schema_artifact_marker(tmp_path):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "invalid_output_schema.zip"
    zip_path.write_bytes(
        _build_skill_zip(
            output_schema_override={
                "type": "object",
                "properties": {
                    "out_path": {"type": "string", "x-type": "binary-artifact"}
                },
            }
        )
    )
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_invalid_output_schema")
    with pytest.raises(ValueError, match="Invalid output schema"):
        validator.validate_skill_dir(
            tmp_path / "stage_invalid_output_schema" / top,
            top,
            require_version=False,
        )


@pytest.mark.parametrize("max_attempt", [1, 10])
def test_accepts_valid_max_attempt(tmp_path, max_attempt):
    validator = SkillPackageValidator()
    zip_path = tmp_path / f"valid_max_attempt_{max_attempt}.zip"
    zip_path.write_bytes(_build_skill_zip(max_attempt=max_attempt))
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / f"stage_valid_max_attempt_{max_attempt}")
    skill_id, version = validator.validate_skill_dir(
        tmp_path / f"stage_valid_max_attempt_{max_attempt}" / top,
        top,
        require_version=False,
    )
    assert skill_id == "demo-temp-skill"
    assert version is None


@pytest.mark.parametrize("max_attempt", [0, -1, "three", 1.5])
def test_rejects_invalid_max_attempt(tmp_path, max_attempt):
    validator = SkillPackageValidator()
    zip_path = tmp_path / "invalid_max_attempt.zip"
    zip_path.write_bytes(_build_skill_zip(max_attempt=max_attempt))
    top = validator.inspect_zip_top_level_from_path(zip_path)
    validator.extract_zip_safe(zip_path, tmp_path / "stage_invalid_max_attempt")
    with pytest.raises(ValueError, match="Invalid runner\\.json manifest"):
        validator.validate_skill_dir(
            tmp_path / "stage_invalid_max_attempt" / top,
            top,
            require_version=False,
        )
