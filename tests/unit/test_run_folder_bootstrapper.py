from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

from server.models import RunLocalSkillSource, SkillManifest
from server.services.orchestration.run_output_schema_service import RunOutputSchemaMaterialization
from server.services.orchestration.run_skill_materialization_service import run_folder_bootstrapper


def _build_skill_dir(tmp_path: Path, skill_id: str = "demo-skill") -> Path:
    skill_dir = tmp_path / skill_id
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {skill_id}\n---\n# Demo\n", encoding="utf-8")
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": skill_id,
                "version": "1.0.0",
                "engines": ["codex"],
                "execution_modes": ["interactive"],
                "schemas": {
                    "input": "assets/input.schema.json",
                    "parameter": "assets/parameter.schema.json",
                    "output": "assets/output.schema.json",
                },
            }
        ),
        encoding="utf-8",
    )
    (assets_dir / "input.schema.json").write_text('{"type":"object"}', encoding="utf-8")
    (assets_dir / "parameter.schema.json").write_text('{"type":"object"}', encoding="utf-8")
    (assets_dir / "output.schema.json").write_text('{"type":"object"}', encoding="utf-8")
    return skill_dir


def test_run_folder_bootstrapper_materializes_installed_skill_once(tmp_path: Path) -> None:
    skill_dir = _build_skill_dir(tmp_path)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill = SkillManifest(
        id="demo-skill",
        path=skill_dir,
        engines=["codex"],
        schemas={
            "input": "assets/input.schema.json",
            "parameter": "assets/parameter.schema.json",
            "output": "assets/output.schema.json",
        },
    )

    with patch(
        "server.services.orchestration.run_skill_materialization_service.run_output_schema_service.materialize",
        return_value=RunOutputSchemaMaterialization(
            business_schema={"type": "object"},
            machine_schema={"type": "object"},
            schema_path=run_dir / ".audit" / "contracts" / "target_output_schema.json",
            schema_relpath=".audit/contracts/target_output_schema.json",
            prompt_summary_markdown="### Output Schema Specification\n\nGenerated summary",
            prompt_summary_path=run_dir / ".audit" / "contracts" / "target_output_schema.md",
            prompt_summary_relpath=".audit/contracts/target_output_schema.md",
        ),
    ) as mock_materialize, patch(
        "server.services.orchestration.run_skill_materialization_service.skill_patcher.patch_skill_md"
    ) as mock_patch:
        ref = run_folder_bootstrapper.materialize_skill(
            skill=skill,
            run_dir=run_dir,
            engine_name="codex",
            execution_mode="interactive",
            source=RunLocalSkillSource.INSTALLED,
        )

    assert ref.snapshot_dir == run_dir / ".codex" / "skills" / "demo-skill"
    assert (ref.snapshot_dir / "SKILL.md").exists()
    mock_materialize.assert_called_once()
    materialize_kwargs = mock_materialize.call_args.kwargs
    assert materialize_kwargs["run_dir"] == run_dir
    assert materialize_kwargs["execution_mode"] == "interactive"
    assert materialize_kwargs["skill"].path == ref.snapshot_dir
    mock_patch.assert_called_once_with(
        ref.snapshot_dir,
        [],
        execution_mode="interactive",
        output_schema_summary_markdown="### Output Schema Specification\n\nGenerated summary",
    )


def test_run_folder_bootstrapper_materializes_temp_skill_package(tmp_path: Path) -> None:
    skill_id = "demo-skill"
    skill_dir = _build_skill_dir(tmp_path, skill_id=skill_id)
    package_bytes = io.BytesIO()
    with zipfile.ZipFile(package_bytes, "w") as zf:
        for path in skill_dir.rglob("*"):
            if path.is_file():
                zf.write(path, arcname=f"{skill_id}/{path.relative_to(skill_dir).as_posix()}")

    run_dir = tmp_path / "run"
    run_dir.mkdir()

    manifest, ref = run_folder_bootstrapper.materialize_temp_skill_package(
        package_bytes=package_bytes.getvalue(),
        run_dir=run_dir,
        engine_name="codex",
        execution_mode="interactive",
        source=RunLocalSkillSource.TEMP_UPLOAD,
    )

    assert manifest.path == ref.snapshot_dir
    assert (ref.snapshot_dir / "assets" / "runner.json").exists()
    assert (run_dir / ".audit" / "contracts" / "target_output_schema.json").exists()
    assert (run_dir / ".audit" / "contracts" / "target_output_schema.md").exists()
