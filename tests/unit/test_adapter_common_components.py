from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from server.models import SkillManifest
from server.runtime.adapter.common.prompt_builder_common import (
    build_prompt_contexts,
    render_template,
    resolve_template_text,
)
from server.runtime.adapter.common.session_codec_common import (
    extract_by_regex,
    first_json_line,
    scan_json_lines_for_session_id,
)
from server.runtime.adapter.common.workspace_provisioner_common import install_skill_package


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


def test_workspace_provisioner_common_installs_and_patches(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Demo", encoding="utf-8")
    (skill_dir / "output.schema.json").write_text('{"type":"object"}', encoding="utf-8")
    skill = SkillManifest(
        id="demo",
        path=skill_dir,
        schemas={"output": "output.schema.json"},
    )
    target = tmp_path / ".engine" / "skills" / "demo"

    with patch(
        "server.runtime.adapter.common.workspace_provisioner_common.skill_patcher.load_output_schema",
        return_value={"type": "object"},
    ) as mock_load, patch(
        "server.runtime.adapter.common.workspace_provisioner_common.skill_patcher.patch_skill_md",
    ) as mock_patch:
        result = install_skill_package(
            skill=skill,
            skills_target_dir=target,
            execution_mode="auto",
            artifacts=[],
        )

    assert result == target
    assert (target / "SKILL.md").exists()
    mock_load.assert_called_once()
    mock_patch.assert_called_once()
