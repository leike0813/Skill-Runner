from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from server.engines.claude.adapter.execution_adapter import ClaudeExecutionAdapter
from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.engines.codex.adapter.sandbox_probe import CodexSandboxProbeResult
from server.engines.gemini.adapter.execution_adapter import GeminiExecutionAdapter
from server.engines.opencode.adapter.execution_adapter import OpencodeExecutionAdapter
from server.engines.qwen.adapter.execution_adapter import QwenExecutionAdapter
from server.models import SkillManifest
from server.runtime.adapter.contracts import AdapterExecutionContext


@pytest.fixture(autouse=True)
def _stable_codex_sandbox_probe(monkeypatch) -> None:
    def _fake_probe(self: CodexExecutionAdapter) -> CodexSandboxProbeResult:
        disabled = os.environ.get("LANDLOCK_ENABLED") == "0"
        return CodexSandboxProbeResult(
            declared_enabled=not disabled,
            available=not disabled,
            status="disabled" if disabled else "available",
            warning_code="CODEX_SANDBOX_DISABLED_BY_ENV" if disabled else None,
            message="sandbox unavailable" if disabled else "sandbox available",
            dependencies={},
            missing_dependencies=[],
            checked_at="2026-04-15T00:00:00Z",
            probe_kind="bubblewrap_smoke",
        )

    monkeypatch.setattr(CodexExecutionAdapter, "get_headless_sandbox_probe", _fake_probe)


def _platform_cmd(path: str) -> str:
    return str(Path(path))


def _write_output_schema(path: Path, payload: dict[str, object] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload
            or {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            }
        ),
        encoding="utf-8",
    )


def _build_ctx(tmp_path: Path, *, relpath: str) -> AdapterExecutionContext:
    run_dir = tmp_path / "run"
    _write_output_schema(run_dir / relpath)
    return AdapterExecutionContext(
        skill=SkillManifest(id="demo-skill", path=tmp_path),
        run_dir=run_dir,
        input_data={},
        options={"__target_output_schema_relpath": relpath},
    )


def _set_output_schema_cli_enabled(adapter: object, enabled: bool) -> None:
    profile = getattr(adapter, "profile")
    command_features = replace(profile.command_features, inject_output_schema_cli=enabled)
    setattr(adapter, "profile", replace(profile, command_features=command_features))


def test_codex_api_start_command_applies_profile_defaults(monkeypatch) -> None:
    adapter = CodexExecutionAdapter()
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.delenv("LANDLOCK_ENABLED", raising=False)
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: ["--json", "--full-auto", "-p", "skill-runner"]
        if use_profile_defaults and action == "start"
        else [],
    )

    command = adapter.build_start_command(
        prompt="hello",
        options={},
        use_profile_defaults=True,
    )

    assert command == [
        _platform_cmd("/usr/bin/codex"),
        "exec",
        "--json",
        "--full-auto",
        "-p",
        "skill-runner",
        "hello",
    ]


def test_codex_harness_start_command_passthrough_without_profile(monkeypatch) -> None:
    adapter = CodexExecutionAdapter()
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.delenv("LANDLOCK_ENABLED", raising=False)
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: ["--json", "-p", "skill-runner"]
        if use_profile_defaults and action == "start"
        else [],
    )

    command = adapter.build_start_command(
        prompt="ignored",
        options={"__harness_mode": True},
        passthrough_args=["exec", "--json", "--full-auto", "-p", "hello"],
        use_profile_defaults=False,
    )

    assert command == [_platform_cmd("/usr/bin/codex"), "exec", "--json", "--full-auto", "-p", "hello"]


def test_codex_harness_start_command_does_not_inject_output_schema(monkeypatch) -> None:
    adapter = CodexExecutionAdapter()
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.delenv("LANDLOCK_ENABLED", raising=False)

    command = adapter.build_start_command(
        prompt="ignored",
        options={"__target_output_schema_relpath": ".audit/contracts/target_output_schema.json"},
        passthrough_args=["exec", "--json", "--full-auto", "-p", "hello"],
        use_profile_defaults=False,
    )

    assert "--output-schema" not in command
    assert command == [_platform_cmd("/usr/bin/codex"), "exec", "--json", "--full-auto", "-p", "hello"]


def test_codex_start_command_fallbacks_full_auto_to_yolo_when_landlock_disabled(monkeypatch) -> None:
    adapter = CodexExecutionAdapter()
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.setenv("LANDLOCK_ENABLED", "0")
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: ["--json", "--full-auto", "-p", "skill-runner"]
        if use_profile_defaults and action == "start"
        else [],
    )

    command = adapter.build_start_command(
        prompt="hello",
        options={},
        use_profile_defaults=True,
    )

    assert "--full-auto" not in command
    assert "--yolo" in command


def test_codex_harness_passthrough_full_auto_fallbacks_to_yolo_when_landlock_disabled(monkeypatch) -> None:
    adapter = CodexExecutionAdapter()
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.setenv("LANDLOCK_ENABLED", "0")

    command = adapter.build_start_command(
        prompt="ignored",
        options={"__harness_mode": True},
        passthrough_args=["exec", "--json", "--full-auto", "-p", "hello"],
        use_profile_defaults=False,
    )

    assert command == [_platform_cmd("/usr/bin/codex"), "exec", "--json", "--yolo", "-p", "hello"]


def test_codex_resume_command_fallbacks_full_auto_to_yolo_when_probe_unavailable(
    monkeypatch,
) -> None:
    from server.models import EngineSessionHandle, EngineSessionHandleType

    adapter = CodexExecutionAdapter()
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.delenv("LANDLOCK_ENABLED", raising=False)
    monkeypatch.setattr(
        adapter,
        "get_headless_sandbox_probe",
        lambda: CodexSandboxProbeResult(
            declared_enabled=True,
            available=False,
            status="unavailable",
            warning_code="CODEX_SANDBOX_RUNTIME_UNAVAILABLE",
            message="bwrap: setting up uid map: Permission denied",
            dependencies={"bubblewrap": True},
            missing_dependencies=[],
            checked_at="2026-04-15T00:00:00Z",
            probe_kind="bubblewrap_smoke",
        ),
    )
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: ["--json", "--full-auto", "-p", "skill-runner"]
        if use_profile_defaults and action == "resume"
        else [],
    )

    command = adapter.build_resume_command(
        prompt="next turn",
        options={},
        session_handle=EngineSessionHandle(
            engine="codex",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="sess-codex",
            created_at_turn=1,
        ),
        use_profile_defaults=True,
    )

    assert "--full-auto" not in command
    assert "--yolo" in command


def test_gemini_start_command_profile_can_be_disabled(monkeypatch) -> None:
    adapter = GeminiExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/gemini"))
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: ["--yolo", "--model", "gemini-default"]
        if use_profile_defaults and action == "start"
        else [],
    )

    with_profile = adapter.build_start_command(
        prompt="hello",
        options={},
        use_profile_defaults=True,
    )
    without_profile = adapter.build_start_command(
        prompt="hello",
        options={},
        use_profile_defaults=False,
    )

    assert with_profile == [_platform_cmd("/usr/bin/gemini"), "--yolo", "--model", "gemini-default", "hello"]
    assert without_profile == [_platform_cmd("/usr/bin/gemini"), "hello"]


def test_codex_resume_command_preserves_profile_flags(monkeypatch) -> None:
    from server.models import EngineSessionHandle, EngineSessionHandleType

    adapter = CodexExecutionAdapter()
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.delenv("LANDLOCK_ENABLED", raising=False)
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: ["--json", "--full-auto", "-p", "skill-runner", "--profile=other"]
        if use_profile_defaults and action == "resume"
        else [],
    )

    command = adapter.build_resume_command(
        prompt="next turn",
        options={},
        session_handle=EngineSessionHandle(
            engine="codex",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="sess-codex",
            created_at_turn=1,
        ),
        use_profile_defaults=True,
    )

    assert command == [
        _platform_cmd("/usr/bin/codex"),
        "exec",
        "-p",
        "skill-runner",
        "--profile=other",
        "resume",
        "--json",
        "--full-auto",
        "sess-codex",
        "next turn",
    ]
    assert "-p" in command
    assert "--profile=other" in command


def test_codex_start_command_injects_output_schema_when_available(monkeypatch, tmp_path: Path) -> None:
    adapter = CodexExecutionAdapter()
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.delenv("LANDLOCK_ENABLED", raising=False)
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: ["--json", "--full-auto", "-p", "skill-runner"]
        if use_profile_defaults and action == "start"
        else [],
    )

    ctx = _build_ctx(tmp_path, relpath=".audit/contracts/target_output_schema.json")
    command = adapter.build_start_command(ctx=ctx, prompt="hello", options=ctx.options, use_profile_defaults=True)

    assert command == [
        _platform_cmd("/usr/bin/codex"),
        "exec",
        "--json",
        "--full-auto",
        "-p",
        "skill-runner",
        "--output-schema",
        ".audit/contracts/target_output_schema.codex_compatible.json",
        "hello",
    ]


def test_codex_start_command_skips_output_schema_when_profile_disabled(monkeypatch, tmp_path: Path) -> None:
    adapter = CodexExecutionAdapter()
    _set_output_schema_cli_enabled(adapter, False)
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.delenv("LANDLOCK_ENABLED", raising=False)
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: ["--json", "--full-auto", "-p", "skill-runner"]
        if use_profile_defaults and action == "start"
        else [],
    )

    ctx = _build_ctx(tmp_path, relpath=".audit/contracts/target_output_schema.json")
    command = adapter.build_start_command(ctx=ctx, prompt="hello", options=ctx.options, use_profile_defaults=True)

    assert "--output-schema" not in command


def test_codex_resume_command_does_not_inject_output_schema_when_available(monkeypatch, tmp_path: Path) -> None:
    from server.models import EngineSessionHandle, EngineSessionHandleType

    adapter = CodexExecutionAdapter()
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.delenv("LANDLOCK_ENABLED", raising=False)
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: ["--json", "--full-auto", "-p", "skill-runner"]
        if use_profile_defaults and action == "resume"
        else [],
    )

    ctx = _build_ctx(tmp_path, relpath=".audit/contracts/target_output_schema.json")
    command = adapter.build_resume_command(
        ctx=ctx,
        prompt="next turn",
        options=ctx.options,
        session_handle=EngineSessionHandle(
            engine="codex",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="sess-codex",
            created_at_turn=1,
        ),
        use_profile_defaults=True,
    )

    assert command == [
        _platform_cmd("/usr/bin/codex"),
        "exec",
        "-p",
        "skill-runner",
        "resume",
        "--json",
        "--full-auto",
        "sess-codex",
        "next turn",
    ]
    assert "--output-schema" not in command


def test_qwen_harness_resume_command_uses_passthrough_only(monkeypatch) -> None:
    from server.models import EngineSessionHandle, EngineSessionHandleType

    adapter = QwenExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/qwen"))

    command = adapter.build_resume_command(
        prompt="next turn",
        options={"__harness_mode": True},
        session_handle=EngineSessionHandle(
            engine="qwen",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="sess-qwen",
            created_at_turn=1,
        ),
        passthrough_args=["--custom-flag"],
        use_profile_defaults=False,
    )

    assert command == [
        _platform_cmd("/usr/bin/qwen"),
        "--custom-flag",
        "--resume",
        "sess-qwen",
        "-p",
        "next turn",
    ]
    assert "--yolo" not in command
    assert "--thinking" not in command


def test_opencode_start_command_includes_run_format_and_model(monkeypatch) -> None:
    adapter = OpencodeExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/opencode"))
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: ["--format", "json"]
        if use_profile_defaults and action == "start"
        else [],
    )

    command = adapter.build_start_command(
        prompt="hello",
        options={"model": "openai/gpt-5"},
        use_profile_defaults=True,
    )

    assert command == [
        _platform_cmd("/usr/bin/opencode"),
        "run",
        "--format",
        "json",
        "--model",
        "openai/gpt-5",
        "hello",
    ]


def test_opencode_harness_resume_command_uses_session_and_passthrough_flags(monkeypatch) -> None:
    from server.models import EngineSessionHandle, EngineSessionHandleType

    adapter = OpencodeExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/opencode"))
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: ["--should-not-appear"]
        if use_profile_defaults and action == "resume"
        else [],
    )

    command = adapter.build_resume_command(
        prompt="next turn",
        options={},
        session_handle=EngineSessionHandle(
            engine="opencode",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="ses-123",
            created_at_turn=1,
        ),
        passthrough_args=[
            "run",
            "--session",
            "old-session",
            "--format",
            "json",
            "--custom-flag",
            "--model",
            "google/gemini-3.1-pro-preview",
            "ignored-positional",
        ],
        use_profile_defaults=False,
    )

    assert command == [
        _platform_cmd("/usr/bin/opencode"),
        "run",
        "--session=ses-123",
        "--format",
        "json",
        "--custom-flag",
        "--model",
        "google/gemini-3.1-pro-preview",
        "next turn",
    ]


def test_qwen_start_command_uses_headless_stream_json_flags(monkeypatch) -> None:
    adapter = QwenExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/qwen"))

    command = adapter.build_start_command(
        prompt="hello",
        options={"model": "coder-model"},
    )

    assert command == [
        _platform_cmd("/usr/bin/qwen"),
        "--output-format",
        "stream-json",
        "--approval-mode",
        "yolo",
        "-p",
        "hello",
    ]


def test_qwen_resume_command_uses_resume_flag_and_prompt(monkeypatch) -> None:
    from server.models import EngineSessionHandle, EngineSessionHandleType

    adapter = QwenExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/qwen"))

    command = adapter.build_resume_command(
        prompt="next turn",
        options={},
        session_handle=EngineSessionHandle(
            engine="qwen",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="sess-qwen",
            created_at_turn=1,
        ),
        use_profile_defaults=True,
    )

    assert command == [
        _platform_cmd("/usr/bin/qwen"),
        "--output-format",
        "stream-json",
        "--approval-mode",
        "yolo",
        "--resume",
        "sess-qwen",
        "-p",
        "next turn",
    ]


def test_claude_start_command_uses_profile_command_defaults(monkeypatch) -> None:
    adapter = ClaudeExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/claude"))
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: [
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        if use_profile_defaults and action == "start"
        else [],
    )

    command = adapter.build_start_command(
        prompt="hello",
        options={"model": "claude-sonnet", "model_reasoning_effort": "high"},
        use_profile_defaults=True,
    )

    assert command == [
        _platform_cmd("/usr/bin/claude"),
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--effort",
        "high",
        "hello",
    ]


def test_claude_start_command_injects_json_schema_when_available(monkeypatch, tmp_path) -> None:
    adapter = ClaudeExecutionAdapter()
    _set_output_schema_cli_enabled(adapter, True)
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/claude"))
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: [
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        if use_profile_defaults and action == "start"
        else [],
    )

    run_dir = tmp_path / "run-claude-start"
    _write_output_schema(run_dir / ".audit" / "contracts" / "target_output_schema.json")
    ctx = AdapterExecutionContext(
        skill=SkillManifest(id="demo-skill", path=tmp_path),
        run_dir=run_dir,
        input_data={},
        options={
            "model_reasoning_effort": "high",
            "__target_output_schema_relpath": ".audit/contracts/target_output_schema.json",
        },
    )

    command = adapter.build_start_command(
        ctx=ctx,
        prompt="hello",
        options=ctx.options,
        use_profile_defaults=True,
    )

    assert command[:-2] == [
        _platform_cmd("/usr/bin/claude"),
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--effort",
        "high",
        "--json-schema",
    ]
    assert json.loads(command[-2]) == {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    assert command[-1] == "hello"


def test_claude_passthrough_start_command_does_not_inject_json_schema(monkeypatch) -> None:
    adapter = ClaudeExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/claude"))

    command = adapter.build_start_command(
        prompt="ignored",
        options={"__target_output_schema_relpath": ".audit/contracts/target_output_schema.json"},
        passthrough_args=["-p", "--output-format", "stream-json", "--verbose", "hello"],
        use_profile_defaults=False,
    )

    assert "--json-schema" not in command
    assert command == [
        _platform_cmd("/usr/bin/claude"),
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "hello",
    ]


def test_claude_start_command_skips_json_schema_when_profile_disabled(monkeypatch, tmp_path) -> None:
    adapter = ClaudeExecutionAdapter()
    _set_output_schema_cli_enabled(adapter, False)
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/claude"))
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: [
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        if use_profile_defaults and action == "start"
        else [],
    )

    run_dir = tmp_path / "run-claude-start"
    _write_output_schema(run_dir / ".audit" / "contracts" / "target_output_schema.json")
    ctx = AdapterExecutionContext(
        skill=SkillManifest(id="demo-skill", path=tmp_path),
        run_dir=run_dir,
        input_data={},
        options={"__target_output_schema_relpath": ".audit/contracts/target_output_schema.json"},
    )

    command = adapter.build_start_command(
        ctx=ctx,
        prompt="hello",
        options=ctx.options,
        use_profile_defaults=True,
    )

    assert "--json-schema" not in command


def test_claude_resume_command_injects_json_schema_when_available(monkeypatch, tmp_path) -> None:
    from server.models import EngineSessionHandle, EngineSessionHandleType

    adapter = ClaudeExecutionAdapter()
    _set_output_schema_cli_enabled(adapter, True)
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/claude"))
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: [
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        if use_profile_defaults and action == "resume"
        else [],
    )

    run_dir = tmp_path / "run-claude-resume"
    _write_output_schema(run_dir / ".audit" / "contracts" / "target_output_schema.json")
    ctx = AdapterExecutionContext(
        skill=SkillManifest(id="demo-skill", path=tmp_path),
        run_dir=run_dir,
        input_data={},
        options={"__target_output_schema_relpath": ".audit/contracts/target_output_schema.json"},
    )

    command = adapter.build_resume_command(
        ctx=ctx,
        prompt="second turn",
        options=ctx.options,
        session_handle=EngineSessionHandle(
            engine="claude",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="session-claude",
            created_at_turn=1,
        ),
        use_profile_defaults=True,
    )

    assert command[:-2] == [
        _platform_cmd("/usr/bin/claude"),
        "--resume",
        "session-claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--json-schema",
    ]
    assert json.loads(command[-2]) == {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }
    assert command[-1] == "second turn"
