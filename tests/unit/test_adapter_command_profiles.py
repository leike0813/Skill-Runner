from __future__ import annotations

from pathlib import Path

from server.engines.claude.adapter.execution_adapter import ClaudeExecutionAdapter
from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.engines.gemini.adapter.execution_adapter import GeminiExecutionAdapter
from server.engines.iflow.adapter.execution_adapter import IFlowExecutionAdapter
from server.engines.opencode.adapter.execution_adapter import OpencodeExecutionAdapter
from server.engines.qwen.adapter.execution_adapter import QwenExecutionAdapter


def _platform_cmd(path: str) -> str:
    return str(Path(path))


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


def test_codex_start_command_injects_output_schema_when_available(monkeypatch) -> None:
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
        options={"__target_output_schema_relpath": ".audit/contracts/target_output_schema.json"},
        use_profile_defaults=True,
    )

    assert command == [
        _platform_cmd("/usr/bin/codex"),
        "exec",
        "--json",
        "--full-auto",
        "-p",
        "skill-runner",
        "--output-schema",
        ".audit/contracts/target_output_schema.json",
        "hello",
    ]


def test_codex_resume_command_injects_output_schema_when_available(monkeypatch) -> None:
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

    command = adapter.build_resume_command(
        prompt="next turn",
        options={"__target_output_schema_relpath": ".audit/contracts/target_output_schema.json"},
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
        "--output-schema",
        ".audit/contracts/target_output_schema.json",
        "sess-codex",
        "next turn",
    ]


def test_iflow_harness_resume_command_uses_passthrough_only(monkeypatch) -> None:
    from server.models import EngineSessionHandle, EngineSessionHandleType

    adapter = IFlowExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/iflow"))
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: ["--yolo", "--thinking"]
        if use_profile_defaults and action == "resume"
        else [],
    )

    command = adapter.build_resume_command(
        prompt="next turn",
        options={"__harness_mode": True},
        session_handle=EngineSessionHandle(
            engine="iflow",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="sess-iflow",
            created_at_turn=1,
        ),
        passthrough_args=["--custom-flag"],
        use_profile_defaults=False,
    )

    assert command == [
        _platform_cmd("/usr/bin/iflow"),
        "--resume",
        "sess-iflow",
        "--custom-flag",
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
            "json",
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
        "json",
        "--verbose",
        "--effort",
        "high",
        "hello",
    ]


def test_claude_start_command_injects_json_schema_when_available(monkeypatch) -> None:
    adapter = ClaudeExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/claude"))
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: [
            "-p",
            "--output-format",
            "json",
            "--verbose",
        ]
        if use_profile_defaults and action == "start"
        else [],
    )

    command = adapter.build_start_command(
        prompt="hello",
        options={
            "model_reasoning_effort": "high",
            "__target_output_schema_relpath": ".audit/contracts/target_output_schema.json",
        },
        use_profile_defaults=True,
    )

    assert command == [
        _platform_cmd("/usr/bin/claude"),
        "-p",
        "--output-format",
        "json",
        "--verbose",
        "--effort",
        "high",
        "--json-schema",
        ".audit/contracts/target_output_schema.json",
        "hello",
    ]


def test_claude_passthrough_start_command_does_not_inject_json_schema(monkeypatch) -> None:
    adapter = ClaudeExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/claude"))

    command = adapter.build_start_command(
        prompt="ignored",
        options={"__target_output_schema_relpath": ".audit/contracts/target_output_schema.json"},
        passthrough_args=["-p", "--output-format", "json", "--verbose", "hello"],
        use_profile_defaults=False,
    )

    assert "--json-schema" not in command
    assert command == [
        _platform_cmd("/usr/bin/claude"),
        "-p",
        "--output-format",
        "json",
        "--verbose",
        "hello",
    ]


def test_claude_resume_command_injects_json_schema_when_available(monkeypatch) -> None:
    from server.models import EngineSessionHandle, EngineSessionHandleType

    adapter = ClaudeExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/claude"))
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_flags",
        lambda *, action, use_profile_defaults: [
            "-p",
            "--output-format",
            "json",
            "--verbose",
        ]
        if use_profile_defaults and action == "resume"
        else [],
    )

    command = adapter.build_resume_command(
        prompt="second turn",
        options={"__target_output_schema_relpath": ".audit/contracts/target_output_schema.json"},
        session_handle=EngineSessionHandle(
            engine="claude",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="session-claude",
            created_at_turn=1,
        ),
        use_profile_defaults=True,
    )

    assert command == [
        _platform_cmd("/usr/bin/claude"),
        "--resume",
        "session-claude",
        "-p",
        "--output-format",
        "json",
        "--verbose",
        "--json-schema",
        ".audit/contracts/target_output_schema.json",
        "second turn",
    ]
