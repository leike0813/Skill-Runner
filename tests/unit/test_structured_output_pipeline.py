from __future__ import annotations

import json
from pathlib import Path

from server.runtime.adapter.common.structured_output_pipeline import structured_output_pipeline


def _write_canonical_interactive_schema(run_dir: Path) -> str:
    relpath = ".audit/contracts/target_output_schema.json"
    schema_path = run_dir / relpath
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(
        json.dumps(
            {
                "oneOf": [
                    {
                        "type": "object",
                        "properties": {
                            "__SKILL_DONE__": {"const": True},
                            "value": {"type": "string"},
                            "report_path": {"type": "string", "x-type": "artifact"},
                        },
                        "required": ["__SKILL_DONE__", "value"],
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "properties": {
                            "__SKILL_DONE__": {"const": False},
                            "message": {"type": "string", "minLength": 1},
                            "ui_hints": {
                                "type": "object",
                                "properties": {
                                    "kind": {"type": "string"},
                                    "prompt": {"type": "string"},
                                    "hint": {"type": "string"},
                                    "options": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "label": {"type": "string"},
                                                "value": {"type": "string"},
                                            },
                                            "required": ["label", "value"],
                                            "additionalProperties": False,
                                        },
                                    },
                                },
                                "required": ["kind"],
                                "additionalProperties": True,
                            },
                        },
                        "required": ["__SKILL_DONE__", "message", "ui_hints"],
                        "additionalProperties": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return relpath


def test_noop_engine_passthrough_keeps_canonical_artifacts_and_payload(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    relpath = _write_canonical_interactive_schema(run_dir)
    summary_relpath = ".audit/contracts/target_output_schema.md"
    (run_dir / summary_relpath).write_text("canonical summary", encoding="utf-8")

    artifacts = structured_output_pipeline.resolve_artifacts(
        engine_name="gemini",
        run_dir=run_dir,
        options={
            "execution_mode": "interactive",
            "__target_output_schema_relpath": relpath,
            "__target_output_schema_summary_relpath": summary_relpath,
        },
    )

    assert artifacts.effective_schema_relpath == relpath
    assert artifacts.effective_summary_relpath == summary_relpath
    assert artifacts.effective_summary_markdown == "canonical summary"

    payload = {"__SKILL_DONE__": True, "value": "ok"}
    assert (
        structured_output_pipeline.canonicalize_payload(
            engine_name="gemini",
            run_dir=run_dir,
            options={"execution_mode": "interactive", "__target_output_schema_relpath": relpath},
            payload=payload,
        )
        == payload
    )


def test_codex_compat_translation_materializes_engine_specific_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    relpath = _write_canonical_interactive_schema(run_dir)

    artifacts = structured_output_pipeline.resolve_artifacts(
        engine_name="codex",
        run_dir=run_dir,
        options={"execution_mode": "interactive", "__target_output_schema_relpath": relpath},
    )

    assert artifacts.effective_schema_relpath == ".audit/contracts/target_output_schema.codex_compatible.json"
    assert artifacts.effective_summary_relpath == ".audit/contracts/target_output_schema.codex_compatible.md"
    compat_schema = json.loads(artifacts.effective_schema_path.read_text(encoding="utf-8"))

    assert compat_schema["type"] == "object"
    assert compat_schema["additionalProperties"] is False
    assert set(compat_schema["required"]) == set(compat_schema["properties"])
    assert "oneOf" not in compat_schema
    assert "allOf" not in compat_schema
    assert "__SKILL_DONE__" in compat_schema["properties"]
    assert "message" in compat_schema["properties"]
    assert "ui_hints" in compat_schema["properties"]
    ui_hints_schema = compat_schema["properties"]["ui_hints"]["anyOf"][0]
    assert ui_hints_schema["type"] == "object"
    assert ui_hints_schema["additionalProperties"] is False

    summary = artifacts.effective_summary_markdown
    assert "Codex structured output compatibility contract" in summary
    assert "Inactive branch fields must be explicit `null` values." in summary
    assert "Pending branch example" in summary


def test_codex_payload_canonicalizer_projects_compat_final_shape_back_to_canonical(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    relpath = _write_canonical_interactive_schema(run_dir)

    canonical = structured_output_pipeline.canonicalize_payload(
        engine_name="codex",
        run_dir=run_dir,
        options={"execution_mode": "interactive", "__target_output_schema_relpath": relpath},
        payload={
            "__SKILL_DONE__": True,
            "value": "done",
            "report_path": "/tmp/report.md",
            "message": None,
            "ui_hints": None,
        },
    )

    assert canonical == {
        "__SKILL_DONE__": True,
        "value": "done",
        "report_path": "/tmp/report.md",
    }


def test_codex_payload_canonicalizer_projects_compat_pending_shape_back_to_canonical(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    relpath = _write_canonical_interactive_schema(run_dir)

    canonical = structured_output_pipeline.canonicalize_payload(
        engine_name="codex",
        run_dir=run_dir,
        options={"execution_mode": "interactive", "__target_output_schema_relpath": relpath},
        payload={
            "__SKILL_DONE__": False,
            "value": None,
            "report_path": None,
            "message": "Choose one option.",
            "ui_hints": {
                "kind": "choose_one",
                "prompt": None,
                "hint": "Pick one.",
                "options": [{"label": "Continue", "value": "continue"}],
                "files": None,
            },
        },
    )

    assert canonical == {
        "__SKILL_DONE__": False,
        "message": "Choose one option.",
        "ui_hints": {
            "kind": "choose_one",
            "hint": "Pick one.",
            "options": [{"label": "Continue", "value": "continue"}],
        },
    }
