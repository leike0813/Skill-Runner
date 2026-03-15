from __future__ import annotations

import json
from pathlib import Path

import pytest
from server.models import SkillManifest
from server.runtime.adapter.common.prompt_builder_common import (
    _normalize_prompt_file_path,
    build_prompt_contexts,
    normalize_prompt_file_input_context,
    render_template,
    resolve_template_text,
)
from server.runtime.adapter.common.session_codec_common import (
    extract_by_regex,
    first_json_line,
    scan_json_lines_for_session_id,
)
from server.runtime.adapter.common.run_folder_validator_common import (
    validate_run_folder_contract,
)


def test_prompt_builder_common_resolves_template_and_context(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "input.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}, "required": []}),
        encoding="utf-8",
    )
    skill = SkillManifest(id="demo", path=skill_dir, schemas={"input": "input.schema.json"})
    template_path = tmp_path / "default.j2"
    template_path.write_text("{{ skill_id }}::{{ run_dir }}", encoding="utf-8")

    input_ctx, parameter_ctx = build_prompt_contexts(
        skill=skill,
        run_dir=tmp_path,
        input_data={"parameter": {}},
        merge_input_if_no_parameter_schema=True,
    )
    assert isinstance(input_ctx, dict)
    assert isinstance(parameter_ctx, dict)

    template_text = resolve_template_text(
        skill=skill,
        engine_key="codex",
        default_template_path=template_path,
        fallback_inline="fallback",
    )
    rendered = render_template(template_text, skill=skill, skill_id=skill.id, run_dir=str(tmp_path))
    assert rendered.startswith("demo::")


def test_normalize_prompt_file_path_for_windows_and_posix() -> None:
    raw_windows = r"C:\runs\abc\uploads\inputs\source_path\paper.md"
    raw_posix = "C:/runs/abc/uploads/inputs/source_path/paper.md"
    assert _normalize_prompt_file_path(raw_posix, platform_name="nt") == raw_windows
    assert _normalize_prompt_file_path(raw_windows, platform_name="posix") == raw_posix


def test_normalize_prompt_file_input_context_only_updates_file_sources(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "input.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "source_path": {"type": "string", "x-input-source": "file"},
                    "language": {"type": "string", "x-input-source": "inline"},
                },
                "required": [],
            }
        ),
        encoding="utf-8",
    )
    skill = SkillManifest(id="demo", path=skill_dir, schemas={"input": "input.schema.json"})
    input_ctx = {
        "source_path": "C:/runs/abc/uploads/inputs/source_path/paper.md",
        "language": "zh-CN",
    }
    normalized = normalize_prompt_file_input_context(
        skill=skill,
        input_ctx=input_ctx,
        platform_name="nt",
    )
    assert normalized["source_path"] == r"C:\runs\abc\uploads\inputs\source_path\paper.md"
    assert normalized["language"] == "zh-CN"
    assert input_ctx["source_path"] == "C:/runs/abc/uploads/inputs/source_path/paper.md"


def test_session_codec_common_helpers() -> None:
    event = first_json_line('{"type":"thread.started","thread_id":"t1"}\n', error_prefix="ERR")
    assert event["type"] == "thread.started"
    session_id = scan_json_lines_for_session_id(
        '{"session_id":"s1"}\n',
        finder=lambda payload: str(payload.get("session_id")) if payload.get("session_id") else None,
        error_prefix="ERR",
    )
    assert session_id == "s1"
    assert extract_by_regex('{"session-id":"abc"}', pattern=r'"session-id":"([^"]+)"', error_message="ERR") == "abc"


def test_run_folder_validator_common_accepts_minimal_execution_contract(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Demo", encoding="utf-8")
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": "demo",
                "version": "1.0.0",
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
    skill = SkillManifest(
        id="demo",
        path=skill_dir,
        schemas={"output": "assets/output.schema.json"},
    )
    config_path = tmp_path / ".engine" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    result = validate_run_folder_contract(skill=skill, config_path=config_path)
    assert result == skill_dir.resolve()


def test_run_folder_validator_common_rejects_missing_schema_file(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Demo", encoding="utf-8")
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": "demo",
                "version": "1.0.0",
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
    config_path = tmp_path / ".engine" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")
    skill = SkillManifest(id="demo", path=skill_dir)

    with pytest.raises(RuntimeError, match="RUN_FOLDER_INVALID"):
        validate_run_folder_contract(skill=skill, config_path=config_path)
