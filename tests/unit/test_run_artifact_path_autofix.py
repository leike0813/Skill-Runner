import json

from server.models import SkillManifest
from server.services.orchestration.run_artifact_path_autofix import (
    BUNDLE_ASSEMBLY_MANIFEST_NOT_FLAT_OBJECT,
    resolve_output_artifact_paths,
)


def _skill_with_output_schema(tmp_path, output_schema):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "output.schema.json").write_text(
        json.dumps(output_schema),
        encoding="utf-8",
    )
    return SkillManifest(
        id="test-skill",
        path=skill_dir,
        schemas={"output": "output.schema.json"},
    )


def test_resolve_output_artifact_paths_expands_artifact_manifest(tmp_path):
    run_dir = tmp_path / "run"
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    (artifacts_dir / "a.txt").write_text("a", encoding="utf-8")
    (artifacts_dir / "b.txt").write_text("b", encoding="utf-8")
    manifest_path = artifacts_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps({"a": "artifacts/a.txt", "b": "artifacts/b.txt"}),
        encoding="utf-8",
    )
    skill = _skill_with_output_schema(
        tmp_path,
        {
            "type": "object",
            "properties": {
                "manifest_path": {
                    "type": "string",
                    "x-type": "artifact",
                    "x-role": "artifact-manifest",
                },
            },
            "required": ["manifest_path"],
        },
    )

    result = resolve_output_artifact_paths(
        skill=skill,
        run_dir=run_dir,
        output_data={"manifest_path": str(manifest_path)},
    )

    assert result.output_data["manifest_path"] == "artifacts/manifest.json"
    assert result.artifacts == [
        "artifacts/a.txt",
        "artifacts/b.txt",
        "artifacts/manifest.json",
    ]
    assert result.assembly_errors == []


def test_resolve_output_artifact_paths_rejects_nested_artifact_manifest(tmp_path):
    run_dir = tmp_path / "run"
    artifacts_dir = run_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    manifest_path = artifacts_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps({"nested": {"path": "artifacts/a.txt"}}),
        encoding="utf-8",
    )
    skill = _skill_with_output_schema(
        tmp_path,
        {
            "type": "object",
            "properties": {
                "manifest_path": {
                    "type": "string",
                    "x-type": "artifact",
                    "x-role": "artifact-manifest",
                },
            },
            "required": ["manifest_path"],
        },
    )

    result = resolve_output_artifact_paths(
        skill=skill,
        run_dir=run_dir,
        output_data={"manifest_path": "artifacts/manifest.json"},
    )

    assert BUNDLE_ASSEMBLY_MANIFEST_NOT_FLAT_OBJECT in result.warnings
    assert result.assembly_errors
    assert BUNDLE_ASSEMBLY_MANIFEST_NOT_FLAT_OBJECT in result.assembly_errors[0]

