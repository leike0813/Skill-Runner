import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from jsonschema import Draft7Validator  # type: ignore[import-untyped]

from server.services.skill.skill_package_validator import SkillPackageValidator


SCRIPTS_DIR = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "skill-converter-agent"
    / "scripts"
)
EMBEDDED_VALIDATOR_PATH = SCRIPTS_DIR / "embedded_skill_package_validator.py"
FINAL_VALIDATOR_PATH = SCRIPTS_DIR / "validate_converted_skill.py"
ZIP_WRAPPER_PATH = SCRIPTS_DIR / "zip_directory_wrapper.py"
OUTPUT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills"
    / "skill-converter-agent"
    / "assets"
    / "output.schema.json"
)


def _load_embedded_validator_cls():
    spec = importlib.util.spec_from_file_location(
        "embedded_skill_package_validator", EMBEDDED_VALIDATOR_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.EmbeddedSkillPackageValidator


def _build_valid_skill_dir(base_dir: Path, skill_id: str = "demo-skill") -> Path:
    skill_dir = base_dir / skill_id
    (skill_dir / "assets").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_id}\ndescription: demo\n---\n\n# Demo\n",
        encoding="utf-8",
    )
    (skill_dir / "assets" / "input.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (skill_dir / "assets" / "parameter.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (skill_dir / "assets" / "output.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "result_path": {
                        "type": "string",
                        "x-type": "artifact",
                        "x-role": "result",
                        "x-filename": "result.json",
                    }
                },
                "required": ["result_path"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (skill_dir / "assets" / "runner.json").write_text(
        json.dumps(
            {
                "id": skill_id,
                "version": "1.0.0",
                "engines": ["gemini"],
                "execution_modes": ["auto", "interactive"],
                "schemas": {
                    "input": "assets/input.schema.json",
                    "parameter": "assets/parameter.schema.json",
                    "output": "assets/output.schema.json",
                },
                "artifacts": [{"role": "result", "pattern": "result.json", "required": False}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return skill_dir


def _zip_skill_dir(skill_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in skill_dir.rglob("*"):
            if path.is_dir():
                continue
            archive.write(path, arcname=f"{skill_dir.name}/{path.relative_to(skill_dir)}")


def _run_embedded_validate(skill_dir: Path):
    cls = _load_embedded_validator_cls()
    validator = cls()
    return validator.validate_skill_dir(skill_dir, top_level_dir=skill_dir.name, require_version=True)


def _run_project_validate(skill_dir: Path):
    validator = SkillPackageValidator()
    return validator.validate_skill_dir(skill_dir, top_level_dir=skill_dir.name, require_version=True)


def test_embedded_validator_accepts_valid_skill_directory(tmp_path: Path) -> None:
    skill_dir = _build_valid_skill_dir(tmp_path)
    skill_id, version = _run_embedded_validate(skill_dir)
    assert skill_id == "demo-skill"
    assert version == "1.0.0"


def test_embedded_validator_rejects_identity_mismatch(tmp_path: Path) -> None:
    skill_dir = _build_valid_skill_dir(tmp_path)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: other-skill\n---\n\n# Demo\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Skill identity mismatch"):
        _run_embedded_validate(skill_dir)


def test_embedded_validator_parity_with_project_validator(tmp_path: Path) -> None:
    skill_dir = _build_valid_skill_dir(tmp_path)
    cases = []

    valid_dir = tmp_path / "case_valid"
    skill_valid = _build_valid_skill_dir(valid_dir, "valid-skill")
    cases.append(("valid", skill_valid, True))

    bad_id_dir = tmp_path / "case_bad_id"
    skill_bad_id = _build_valid_skill_dir(bad_id_dir, "bad-id-skill")
    runner = json.loads((skill_bad_id / "assets" / "runner.json").read_text(encoding="utf-8"))
    runner["id"] = ""
    (skill_bad_id / "assets" / "runner.json").write_text(
        json.dumps(runner, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    cases.append(("bad_id", skill_bad_id, False))

    missing_schema_dir = tmp_path / "case_missing_schema"
    skill_missing_schema = _build_valid_skill_dir(missing_schema_dir, "missing-schema")
    (skill_missing_schema / "assets" / "output.schema.json").unlink()
    cases.append(("missing_schema", skill_missing_schema, False))

    for _, candidate, expected_valid in cases:
        embedded_ok = True
        project_ok = True
        try:
            _run_embedded_validate(candidate)
        except Exception:
            embedded_ok = False
        try:
            _run_project_validate(candidate)
        except Exception:
            project_ok = False
        assert embedded_ok == project_ok
        assert embedded_ok == expected_valid


def test_final_validator_script_directory_mode_success(tmp_path: Path) -> None:
    skill_dir = _build_valid_skill_dir(tmp_path)
    proc = subprocess.run(
        [
            sys.executable,
            str(FINAL_VALIDATOR_PATH),
            "--skill-path",
            str(skill_dir),
            "--source-type",
            "directory",
            "--require-version",
            "true",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout.strip())
    assert payload["valid"] is True
    assert payload["skill_id"] == "demo-skill"


def test_final_validator_script_zip_mode_success(tmp_path: Path) -> None:
    skill_dir = _build_valid_skill_dir(tmp_path)
    zip_path = tmp_path / "skill.zip"
    _zip_skill_dir(skill_dir, zip_path)

    proc = subprocess.run(
        [
            sys.executable,
            str(FINAL_VALIDATOR_PATH),
            "--skill-path",
            str(zip_path),
            "--source-type",
            "zip",
            "--require-version",
            "true",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout.strip())
    assert payload["valid"] is True
    assert payload["source_type"] == "zip"


def test_zip_wrapper_unpack_mode_success(tmp_path: Path) -> None:
    skill_dir = _build_valid_skill_dir(tmp_path, "wrapped-skill")
    zip_path = tmp_path / "wrapped-skill.zip"
    _zip_skill_dir(skill_dir, zip_path)
    dest_dir = tmp_path / "unpacked"
    proc = subprocess.run(
        [
            sys.executable,
            str(ZIP_WRAPPER_PATH),
            "--mode",
            "unpack",
            "--zip-path",
            str(zip_path),
            "--dest-dir",
            str(dest_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout.strip())
    assert payload["mode"] == "unpack"
    assert payload["top_level_dir"] == "wrapped-skill"
    assert (dest_dir / "wrapped-skill" / "SKILL.md").exists()


def test_zip_wrapper_pack_mode_success(tmp_path: Path) -> None:
    skill_dir = _build_valid_skill_dir(tmp_path, "pack-source")
    output_zip = tmp_path / "artifacts" / "pack-source.zip"
    proc = subprocess.run(
        [
            sys.executable,
            str(ZIP_WRAPPER_PATH),
            "--mode",
            "pack",
            "--source-dir",
            str(skill_dir),
            "--zip-path",
            str(output_zip),
            "--top-level-name",
            "pack-target",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout.strip())
    assert payload["mode"] == "pack"
    assert payload["top_level_dir"] == "pack-target"
    assert output_zip.exists()


def test_output_schema_not_convertible_rejects_package_fields() -> None:
    schema = json.loads(OUTPUT_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)
    valid_payload = {
        "status": "failed",
        "classification": "not_convertible",
        "failure_reason": "requires interactive human decisions",
    }
    assert list(validator.iter_errors(valid_payload)) == []

    invalid_payload = {
        "status": "failed",
        "classification": "not_convertible",
        "failure_reason": "requires interactive human decisions",
        "converted_skill_directory_path": "/tmp/converted_skill",
    }
    errors = list(validator.iter_errors(invalid_payload))
    assert errors


def test_output_schema_success_classes_require_package_fields() -> None:
    schema = json.loads(OUTPUT_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft7Validator(schema)
    missing_fields_payload = {
        "status": "succeeded",
        "classification": "ready_for_auto",
    }
    errors = list(validator.iter_errors(missing_fields_payload))
    assert errors

    valid_payload = {
        "status": "succeeded",
        "classification": "ready_for_auto",
        "converted_skill_package_path": "artifacts/converted_skill.zip",
        "conversion_report_path": "artifacts/conversion_report.md",
    }
    assert list(validator.iter_errors(valid_payload)) == []
