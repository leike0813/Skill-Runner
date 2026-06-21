from __future__ import annotations

import json
from pathlib import Path

import jsonschema  # type: ignore[import-untyped]

from server.models import SkillManifest
from server.services.orchestration.run_output_schema_service import (
    REQUEST_INPUT_TARGET_OUTPUT_SCHEMA_PATH,
    RUN_OPTION_TARGET_OUTPUT_SCHEMA_RELPATH,
    TARGET_OUTPUT_SCHEMA_RELPATH,
    run_output_schema_service,
)


def _build_skill_dir(
    tmp_path: Path,
    *,
    skill_id: str = "demo-skill",
    include_output_schema: bool = True,
) -> Path:
    skill_dir = tmp_path / skill_id
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
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
                    **(
                        {"output": "assets/output.schema.json"}
                        if include_output_schema
                        else {}
                    ),
                },
            }
        ),
        encoding="utf-8",
    )
    (assets_dir / "input.schema.json").write_text('{"type":"object"}', encoding="utf-8")
    (assets_dir / "parameter.schema.json").write_text('{"type":"object"}', encoding="utf-8")
    if include_output_schema:
        (assets_dir / "output.schema.json").write_text(
            json.dumps(
                {
                    "type": "object",
                    "required": ["value", "report_path"],
                    "properties": {
                        "value": {"type": "string", "description": "result value"},
                        "report_path": {
                            "type": "string",
                            "x-type": "artifact",
                            "x-role": "report",
                        },
                    },
                    "additionalProperties": False,
                }
            ),
            encoding="utf-8",
        )
    return skill_dir


def _build_skill_manifest(skill_dir: Path, *, include_output_schema: bool = True) -> SkillManifest:
    schemas = {
        "input": "assets/input.schema.json",
        "parameter": "assets/parameter.schema.json",
    }
    if include_output_schema:
        schemas["output"] = "assets/output.schema.json"
    return SkillManifest(
        id=skill_dir.name,
        path=skill_dir,
        engines=["codex"],
        schemas=schemas,
    )


def test_materialize_auto_schema_artifacts_and_request_input_fields(tmp_path: Path) -> None:
    skill_dir = _build_skill_dir(tmp_path)
    skill = _build_skill_manifest(skill_dir)
    run_dir = tmp_path / "run"
    audit_dir = run_dir / ".audit" / "demo-skill.1"
    input_manifest_path = audit_dir / "input_manifest.json"
    audit_dir.mkdir(parents=True, exist_ok=True)
    input_manifest_path.write_text(
        json.dumps({"request_id": "req-1"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    materialization = run_output_schema_service.materialize(
        skill=skill,
        execution_mode="auto",
        run_dir=run_dir,
        audit_dir=audit_dir,
        input_manifest_path=input_manifest_path,
    )

    expected_relpath = ".audit/demo-skill.1/contracts/target_output_schema.json"
    assert materialization.schema_relpath == expected_relpath
    assert materialization.schema_path == run_dir / expected_relpath
    assert materialization.schema_path is not None
    assert materialization.schema_path.exists()

    payload = json.loads(materialization.schema_path.read_text(encoding="utf-8"))
    assert payload["required"] == ["__SKILL_DONE__", "value", "report_path"]
    assert payload["properties"]["__SKILL_DONE__"]["const"] is True
    assert payload["properties"]["report_path"]["x-type"] == "artifact"
    assert payload["additionalProperties"] is False

    request_payload = json.loads(input_manifest_path.read_text(encoding="utf-8"))
    assert request_payload[REQUEST_INPUT_TARGET_OUTPUT_SCHEMA_PATH] == expected_relpath

    run_options = run_output_schema_service.build_run_option_fields(run_dir=run_dir, audit_dir=audit_dir)
    assert run_options == {
        RUN_OPTION_TARGET_OUTPUT_SCHEMA_RELPATH: expected_relpath,
    }
    assert "### Output Contract Details" in materialization.prompt_contract_markdown
    assert expected_relpath in materialization.prompt_contract_markdown


def test_materialize_schema_artifacts_under_namespaced_audit_dir(tmp_path: Path) -> None:
    skill_dir = _build_skill_dir(tmp_path)
    skill = _build_skill_manifest(skill_dir)
    run_dir = tmp_path / "run"
    audit_dir = run_dir / ".audit" / "demo-skill.1"
    input_manifest_path = audit_dir / "input_manifest.json"
    input_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    input_manifest_path.write_text(
        json.dumps({"request_id": "req-1"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    materialization = run_output_schema_service.materialize(
        skill=skill,
        execution_mode="auto",
        run_dir=run_dir,
        audit_dir=audit_dir,
        input_manifest_path=input_manifest_path,
    )

    expected_relpath = ".audit/demo-skill.1/contracts/target_output_schema.json"
    assert materialization.schema_relpath == expected_relpath
    assert materialization.schema_path == run_dir / expected_relpath
    assert materialization.schema_path.exists()
    assert not (run_dir / TARGET_OUTPUT_SCHEMA_RELPATH).exists()

    request_payload = json.loads(input_manifest_path.read_text(encoding="utf-8"))
    assert request_payload[REQUEST_INPUT_TARGET_OUTPUT_SCHEMA_PATH] == expected_relpath

    run_options = run_output_schema_service.build_run_option_fields(
        run_dir=run_dir,
        audit_dir=audit_dir,
    )
    assert run_options == {
        RUN_OPTION_TARGET_OUTPUT_SCHEMA_RELPATH: expected_relpath,
    }
    assert expected_relpath in materialization.prompt_contract_markdown


def test_materialize_interactive_machine_schema_uses_union_and_keeps_stable_path(tmp_path: Path) -> None:
    skill_dir = _build_skill_dir(tmp_path)
    skill = _build_skill_manifest(skill_dir)
    run_dir = tmp_path / "run"
    audit_dir = run_dir / ".audit" / "demo-skill.1"
    input_manifest_path = audit_dir / "input_manifest.json"
    input_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    input_manifest_path.write_text("{}", encoding="utf-8")

    first = run_output_schema_service.materialize(
        skill=skill,
        execution_mode="interactive",
        run_dir=run_dir,
        audit_dir=audit_dir,
        input_manifest_path=input_manifest_path,
    )
    second = run_output_schema_service.materialize(
        skill=skill,
        execution_mode="interactive",
        run_dir=run_dir,
        audit_dir=audit_dir,
        input_manifest_path=input_manifest_path,
    )

    expected_relpath = ".audit/demo-skill.1/contracts/target_output_schema.json"
    assert first.schema_relpath == second.schema_relpath == expected_relpath
    assert first.schema_path is not None

    payload = json.loads(first.schema_path.read_text(encoding="utf-8"))
    assert payload["oneOf"]
    assert len(payload["oneOf"]) == 2
    final_branch = payload["oneOf"][0]
    pending_branch = payload["oneOf"][1]
    assert final_branch["properties"]["__SKILL_DONE__"]["const"] is True
    assert pending_branch["required"] == ["__SKILL_DONE__", "message", "ui_hints"]
    assert pending_branch["properties"]["__SKILL_DONE__"]["const"] is False
    assert pending_branch["properties"]["message"]["minLength"] == 1
    assert pending_branch["properties"]["ui_hints"]["type"] == "object"

    assert "#### Final Branch Contract" in first.prompt_contract_markdown
    assert "#### Pending Branch Contract" in first.prompt_contract_markdown
    assert "<ASK_USER_YAML>" not in first.prompt_contract_markdown
    assert "Supported `ui_hints.kind` values" in first.prompt_contract_markdown
    assert "Pending branch example" in first.prompt_contract_markdown
    assert '"__SKILL_DONE__": false' in first.prompt_contract_markdown
    assert expected_relpath in first.prompt_contract_markdown
    assert first.prompt_contract_markdown.index("#### Final Branch Contract") < first.prompt_contract_markdown.index(
        "#### Pending Branch Contract"
    )


def test_final_wrapper_injects_done_marker_into_object_union_branches() -> None:
    schema = run_output_schema_service.build_final_wrapper_schema(
        {
            "type": "object",
            "oneOf": [
                {
                    "type": "object",
                    "properties": {
                        "kind": {"const": "ok"},
                        "value": {"type": "string"},
                    },
                    "required": ["kind", "value"],
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "properties": {
                        "kind": {"const": "canceled"},
                        "reason": {"type": "string"},
                    },
                    "required": ["kind", "reason"],
                    "additionalProperties": False,
                },
            ],
        }
    )

    assert schema["required"] == ["__SKILL_DONE__"]
    for branch in schema["oneOf"]:
        assert branch["properties"]["__SKILL_DONE__"]["const"] is True
        assert "__SKILL_DONE__" in branch["required"]

    jsonschema.validate(
        instance={"__SKILL_DONE__": True, "kind": "ok", "value": "done"},
        schema=schema,
    )


def test_materialize_missing_output_schema_skips_artifacts(tmp_path: Path) -> None:
    skill_dir = _build_skill_dir(tmp_path, include_output_schema=False)
    skill = _build_skill_manifest(skill_dir, include_output_schema=False)
    run_dir = tmp_path / "run"
    audit_dir = run_dir / ".audit" / "demo-skill.1"

    materialization = run_output_schema_service.materialize(
        skill=skill,
        execution_mode="auto",
        run_dir=run_dir,
        audit_dir=audit_dir,
    )

    assert materialization.machine_schema is None
    assert materialization.schema_path is None
    assert materialization.prompt_contract_markdown == ""
    assert not (run_dir / TARGET_OUTPUT_SCHEMA_RELPATH).exists()
    assert run_output_schema_service.build_run_option_fields(run_dir=run_dir, audit_dir=audit_dir) == {}
