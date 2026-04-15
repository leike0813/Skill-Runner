from __future__ import annotations

import json
from pathlib import Path

import pytest
from server.engines.claude.adapter.execution_adapter import ClaudeExecutionAdapter
from server.engines.claude.adapter.sandbox_probe import (
    ClaudeSandboxProbeResult,
    write_claude_sandbox_probe,
)
from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.engines.gemini.adapter.execution_adapter import GeminiExecutionAdapter
from server.models import SkillManifest
from server.runtime.adapter.contracts import AdapterExecutionContext
from server.runtime.adapter.common.prompt_builder_common import (
    _normalize_prompt_file_path,
    assemble_prompt,
    build_default_body_prompt,
    build_prompt_render_context,
    build_prompt_contexts,
    normalize_prompt_file_input_context,
    resolve_run_instruction_filename,
    render_run_execution_instructions,
    render_skill_invoke_line,
    render_template,
    resolve_skill_body_prompt_text,
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
    input_ctx, parameter_ctx = build_prompt_contexts(
        skill=skill,
        run_dir=tmp_path,
        input_data={"parameter": {}},
    )
    assert isinstance(input_ctx, dict)
    assert isinstance(parameter_ctx, dict)

    context = {
        "skill": skill,
        "skill_id": skill.id,
        "run_dir": str(tmp_path),
        "input": input_ctx,
        "parameter": parameter_ctx,
    }
    rendered = build_default_body_prompt(profile=CodexExecutionAdapter().profile, context=context)
    assert "# Inputs" in rendered
    assert "# Parameters" in rendered


def test_resolve_skill_body_prompt_text_prefers_engine_prompt_over_common() -> None:
    skill = SkillManifest(
        id="demo",
        entrypoint={
            "prompts": {
                "common": "common prompt",
                "codex": "codex prompt",
            }
        },
    )

    resolved = resolve_skill_body_prompt_text(
        skill=skill,
        engine_name="codex",
    )

    assert resolved == "codex prompt"


def test_resolve_skill_body_prompt_text_falls_back_to_common_prompt() -> None:
    skill = SkillManifest(
        id="demo",
        entrypoint={"prompts": {"common": "common prompt"}},
    )

    resolved = resolve_skill_body_prompt_text(
        skill=skill,
        engine_name="gemini",
    )

    assert resolved == "common prompt"


def test_resolve_skill_body_prompt_text_returns_empty_when_skill_prompt_missing() -> None:
    assert resolve_skill_body_prompt_text(skill=SkillManifest(id="demo"), engine_name="gemini") == ""


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


def test_claude_default_prompt_template_uses_prefix_extra_block(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Demo", encoding="utf-8")
    (skill_dir / "input.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}, "required": []}),
        encoding="utf-8",
    )
    (skill_dir / "parameter.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}, "required": []}),
        encoding="utf-8",
    )
    skill = SkillManifest(
        id="demo-claude-skill",
        path=skill_dir,
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
        },
    )
    adapter = ClaudeExecutionAdapter()
    agent_home = tmp_path / "agent_home"
    agent_home.mkdir(parents=True, exist_ok=True)
    object.__setattr__(adapter.agent_manager.profile, "agent_home", agent_home)
    ctx = AdapterExecutionContext(
        skill=skill,
        run_dir=tmp_path / "run",
        input_data={"input": {}, "parameter": {}},
        options={},
    )

    rendered = adapter.prompt_builder.render(ctx)  # type: ignore[union-attr]
    assert rendered.startswith("/demo-claude-skill\n")
    assert "# Sandbox Policy" in rendered
    assert "Prefer Bash inside the sandbox first." in rendered
    assert "you may retry that command once without sandbox." in rendered
    assert "Do not use unsandboxed fallback for ordinary policy denials" in rendered
    assert "# Inputs" in rendered
    assert "# Parameters" in rendered
    assert "Task: Execute the skill using the above inputs and parameters." in rendered


def test_claude_prompt_builder_uses_common_prompt_when_engine_prompt_missing(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Demo", encoding="utf-8")
    (skill_dir / "input.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}, "required": []}),
        encoding="utf-8",
    )
    (skill_dir / "parameter.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}, "required": []}),
        encoding="utf-8",
    )
    skill = SkillManifest(
        id="demo-common-skill",
        path=skill_dir,
        entrypoint={"prompts": {"common": "COMMON {{ skill.id }} {{ run_dir }}"}},
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
        },
    )
    adapter = ClaudeExecutionAdapter()
    run_dir = tmp_path / "run"
    ctx = AdapterExecutionContext(
        skill=skill,
        run_dir=run_dir,
        input_data={"input": {}, "parameter": {}},
        options={},
    )

    rendered = adapter.prompt_builder.render(ctx)  # type: ignore[union-attr]
    assert rendered == f"/demo-common-skill\nCOMMON demo-common-skill {run_dir}"


def test_claude_default_prompt_template_avoids_sandbox_first_when_probe_unavailable(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Demo", encoding="utf-8")
    (skill_dir / "input.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}, "required": []}),
        encoding="utf-8",
    )
    (skill_dir / "parameter.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}, "required": []}),
        encoding="utf-8",
    )
    skill = SkillManifest(
        id="demo-claude-skill",
        path=skill_dir,
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
        },
    )
    adapter = ClaudeExecutionAdapter()
    agent_home = tmp_path / "agent_home"
    agent_home.mkdir(parents=True, exist_ok=True)
    object.__setattr__(adapter.agent_manager.profile, "agent_home", agent_home)
    write_claude_sandbox_probe(
        agent_home=agent_home,
        probe=ClaudeSandboxProbeResult(
            declared_enabled=True,
            available=False,
            status="unavailable",
            warning_code="CLAUDE_SANDBOX_RUNTIME_UNAVAILABLE",
            message="Claude sandbox runtime unavailable: Failed RTM_NEWADDR.",
            dependencies={"bubblewrap": True, "socat": True},
            missing_dependencies=[],
            checked_at="2026-04-04T00:00:00Z",
            probe_kind="bubblewrap_smoke",
        ),
    )
    ctx = AdapterExecutionContext(
        skill=skill,
        run_dir=tmp_path / "run",
        input_data={"input": {}, "parameter": {}},
        options={},
    )

    rendered = adapter.prompt_builder.render(ctx)  # type: ignore[union-attr]
    assert rendered.startswith("/demo-claude-skill\n")
    assert "Claude sandbox is unavailable in this environment." in rendered
    assert "Execute Bash normally without attempting sandbox-first retries." in rendered
    assert "Prefer Bash inside the sandbox first." not in rendered


def test_build_default_body_prompt_includes_prefix_and_common_template() -> None:
    adapter = ClaudeExecutionAdapter()
    rendered = build_default_body_prompt(
        profile=adapter.profile,
        context={
            "claude_sandbox_available": False,
            "claude_sandbox_message": "sandbox broken",
            "input": {"source_path": "/tmp/paper.md"},
            "parameter": {"language": "zh-CN"},
        },
    )

    assert rendered.startswith("# Sandbox Policy")
    assert "sandbox broken" in rendered
    assert "# Inputs" in rendered
    assert "# Parameters" in rendered


def test_prompt_render_context_exposes_engine_relative_dirs_and_run_instructions(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Demo", encoding="utf-8")
    (skill_dir / "input.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}, "required": []}),
        encoding="utf-8",
    )
    (skill_dir / "parameter.schema.json").write_text(
        json.dumps({"type": "object", "properties": {}, "required": []}),
        encoding="utf-8",
    )
    skill = SkillManifest(
        id="demo-global-prefix",
        path=skill_dir,
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
        },
    )
    run_dir = tmp_path / "run"
    ctx = AdapterExecutionContext(
        skill=skill,
        run_dir=run_dir,
        input_data={"input": {}, "parameter": {}},
        options={"__attempt_number": 1},
    )

    claude_adapter = ClaudeExecutionAdapter()
    claude_context = build_prompt_render_context(ctx=ctx, profile=claude_adapter.profile)
    assert claude_context["engine_id"] == "claude"
    assert claude_context["engine_workspace_dir"] == "./.claude"
    assert claude_context["engine_skills_dir"] == "./.claude/skills"
    assert render_skill_invoke_line(ctx=ctx, profile=claude_adapter.profile) == "/demo-global-prefix"
    assert "./.claude/skills" in render_run_execution_instructions(
        run_dir=run_dir,
        profile=claude_adapter.profile,
        skill=skill,
    )

    gemini_adapter = GeminiExecutionAdapter()
    gemini_context = build_prompt_render_context(ctx=ctx, profile=gemini_adapter.profile)
    assert gemini_context["engine_id"] == "gemini"
    assert gemini_context["engine_workspace_dir"] == "./.gemini"
    assert gemini_context["engine_skills_dir"] == "./.gemini/skills"
    assert render_skill_invoke_line(ctx=ctx, profile=gemini_adapter.profile) == "/demo-global-prefix invoke"

    codex_adapter = CodexExecutionAdapter()
    codex_context = build_prompt_render_context(ctx=ctx, profile=codex_adapter.profile)
    assert codex_context["engine_id"] == "codex"
    assert codex_context["engine_workspace_dir"] == "./.codex"
    assert codex_context["engine_skills_dir"] == "./.codex/skills"
    assert render_skill_invoke_line(ctx=ctx, profile=codex_adapter.profile) == "$demo-global-prefix"


def test_assemble_prompt_puts_invocation_line_first() -> None:
    prompt = assemble_prompt(
        invoke_line="/demo invoke",
        body_prompt="\n\n# Inputs\n- path: demo.txt\n",
    )

    assert prompt == "/demo invoke\n# Inputs\n- path: demo.txt\n"


def test_assemble_prompt_returns_only_invocation_line_when_body_is_blank() -> None:
    assert assemble_prompt(invoke_line="invoke demo", body_prompt="\n\n   \n") == "invoke demo"


def test_resolve_run_instruction_filename_by_engine() -> None:
    assert resolve_run_instruction_filename("claude") == "CLAUDE.md"
    assert resolve_run_instruction_filename("gemini") == "GEMINI.md"
    assert resolve_run_instruction_filename("codex") == "AGENTS.md"


def test_render_run_execution_instructions_exposes_workspace_and_global_policy(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill = SkillManifest(id="demo-skill", path=skill_dir)
    run_dir = tmp_path / "run"

    claude_adapter = ClaudeExecutionAdapter()
    rendered = render_run_execution_instructions(
        run_dir=run_dir,
        profile=claude_adapter.profile,
        skill=skill,
    )

    assert "# Run Execution Instructions" in rendered
    assert f"Current run root: `{run_dir}`" in rendered
    assert "`./.claude`" in rendered
    assert "`./.claude/skills`" in rendered
    assert "prefer calling that tool instead of directly using `read`" in rendered
    assert "runtime-patched `SKILL.md` remains the authoritative source" in rendered
    assert "Proceed autonomously" not in rendered
