from __future__ import annotations

from pathlib import Path

from server.adapters.codex_adapter import CodexAdapter
from server.adapters.gemini_adapter import GeminiAdapter
from server.adapters.iflow_adapter import IFlowAdapter


def test_codex_api_start_command_applies_profile_defaults(monkeypatch) -> None:
    adapter = CodexAdapter()
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.delenv("LANDLOCK_ENABLED", raising=False)
    monkeypatch.setattr(
        "server.adapters.codex_adapter.engine_command_profile.resolve_args",
        lambda **_kwargs: ["--json", "--full-auto", "-p", "skill-runner"],
    )

    command = adapter.build_start_command(
        prompt="hello",
        options={},
        use_profile_defaults=True,
    )

    assert command == [
        "/usr/bin/codex",
        "exec",
        "--json",
        "--full-auto",
        "-p",
        "skill-runner",
        "hello",
    ]


def test_codex_harness_start_command_passthrough_without_profile(monkeypatch) -> None:
    adapter = CodexAdapter()
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.delenv("LANDLOCK_ENABLED", raising=False)
    monkeypatch.setattr(
        "server.adapters.codex_adapter.engine_command_profile.resolve_args",
        lambda **_kwargs: ["--json", "-p", "skill-runner"],
    )

    command = adapter.build_start_command(
        prompt="ignored",
        options={"__harness_mode": True},
        passthrough_args=["exec", "--json", "--full-auto", "-p", "hello"],
        use_profile_defaults=False,
    )

    assert command == ["/usr/bin/codex", "exec", "--json", "--full-auto", "-p", "hello"]


def test_codex_start_command_fallbacks_full_auto_to_yolo_when_landlock_disabled(monkeypatch) -> None:
    adapter = CodexAdapter()
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.setenv("LANDLOCK_ENABLED", "0")
    monkeypatch.setattr(
        "server.adapters.codex_adapter.engine_command_profile.resolve_args",
        lambda **_kwargs: ["--json", "--full-auto", "-p", "skill-runner"],
    )

    command = adapter.build_start_command(
        prompt="hello",
        options={},
        use_profile_defaults=True,
    )

    assert "--full-auto" not in command
    assert "--yolo" in command


def test_codex_harness_passthrough_full_auto_fallbacks_to_yolo_when_landlock_disabled(monkeypatch) -> None:
    adapter = CodexAdapter()
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.setenv("LANDLOCK_ENABLED", "0")

    command = adapter.build_start_command(
        prompt="ignored",
        options={"__harness_mode": True},
        passthrough_args=["exec", "--json", "--full-auto", "-p", "hello"],
        use_profile_defaults=False,
    )

    assert command == ["/usr/bin/codex", "exec", "--json", "--yolo", "-p", "hello"]


def test_gemini_start_command_profile_can_be_disabled(monkeypatch) -> None:
    adapter = GeminiAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/gemini"))
    monkeypatch.setattr(
        "server.adapters.gemini_adapter.engine_command_profile.resolve_args",
        lambda **_kwargs: ["--yolo", "--model", "gemini-default"],
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

    assert with_profile == ["/usr/bin/gemini", "--yolo", "--model", "gemini-default", "hello"]
    assert without_profile == ["/usr/bin/gemini", "hello"]


def test_codex_resume_command_filters_profile_flags(monkeypatch) -> None:
    from server.models import EngineSessionHandle, EngineSessionHandleType

    adapter = CodexAdapter()
    monkeypatch.setattr(adapter, "_resolve_codex_command", lambda: Path("/usr/bin/codex"))
    monkeypatch.delenv("LANDLOCK_ENABLED", raising=False)
    monkeypatch.setattr(
        "server.adapters.codex_adapter.engine_command_profile.resolve_args",
        lambda **_kwargs: ["--json", "--full-auto", "-p", "skill-runner", "--profile=other"],
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
        "/usr/bin/codex",
        "exec",
        "resume",
        "--json",
        "--full-auto",
        "sess-codex",
        "next turn",
    ]
    assert "-p" not in command
    assert "--profile=other" not in command


def test_iflow_harness_resume_command_uses_passthrough_only(monkeypatch) -> None:
    from server.models import EngineSessionHandle, EngineSessionHandleType

    adapter = IFlowAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/iflow"))
    monkeypatch.setattr(
        "server.adapters.iflow_adapter.engine_command_profile.resolve_args",
        lambda **_kwargs: ["--yolo", "--thinking"],
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
        "/usr/bin/iflow",
        "--resume",
        "sess-iflow",
        "--custom-flag",
        "-p",
        "next turn",
    ]
    assert "--yolo" not in command
    assert "--thinking" not in command
