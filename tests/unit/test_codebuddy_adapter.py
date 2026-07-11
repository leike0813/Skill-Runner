import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from server.engines.codebuddy.adapter.execution_adapter import CodeBuddyExecutionAdapter
from server.engines.codebuddy.adapter.stream_framer import CodeBuddyStreamFramer
from server.engines.codebuddy.adapter.stream_parser import CodeBuddyStreamParser
from server.models import EngineSessionHandle, EngineSessionHandleType, SkillManifest
from server.runtime.adapter.contracts import AdapterExecutionContext
from server.runtime.adapter.types import AdapterAuthenticationRequired
from server.services.mcp.registry import McpServerDefinition, ResolvedMcpServer, render_mcp_config
from server.services.orchestration.run_execution_core import validate_runtime_and_model_options


def _ctx(tmp_path: Path, options: dict[str, object] | None = None) -> AdapterExecutionContext:
    skill_dir = tmp_path / "skill"
    (skill_dir / "assets").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
    (skill_dir / "assets" / "runner.json").write_text('{"schemas":{"output":"output.json"}}', encoding="utf-8")
    (skill_dir / "assets" / "output.json").write_text('{"type":"object"}', encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    return AdapterExecutionContext(skill=SkillManifest(id="demo", path=skill_dir), run_dir=run_dir, input_data={}, options=options or {"provider_id": "codebuddy-cn"})


def test_codebuddy_command_contract_is_symmetric(tmp_path: Path, monkeypatch) -> None:
    adapter = CodeBuddyExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/managed/codebuddy"))
    ctx = _ctx(tmp_path, {"provider_id": "codebuddy-cn", "runtime_model": "glm-5.2"})
    start = adapter.command_builder.build_start(ctx, "prompt")
    resume = adapter.command_builder.build_resume(ctx, "reply", EngineSessionHandle(engine="codebuddy", handle_type=EngineSessionHandleType.SESSION_ID, handle_value="session-1"))
    assert start[-1] == "prompt" and resume[-1] == "reply"
    assert "--strict-mcp-config" in start and "--strict-mcp-config" in resume
    assert resume[resume.index("-r") + 1] == "session-1"
    assert "--model" in start and "--continue" not in resume


def test_codebuddy_config_preserves_canonical_skill_snapshot(tmp_path: Path) -> None:
    adapter = CodeBuddyExecutionAdapter()
    ctx = _ctx(tmp_path)
    assert ctx.skill.path is not None
    snapshot = ctx.run_dir / ".codebuddy" / "skills" / ctx.skill.id
    snapshot.parent.mkdir(parents=True)
    shutil.copytree(ctx.skill.path, snapshot)
    ctx = AdapterExecutionContext(
        skill=ctx.skill.model_copy(update={"path": snapshot}),
        run_dir=ctx.run_dir,
        input_data=ctx.input_data,
        options=ctx.options,
    )
    skill_markdown = (snapshot / "SKILL.md").read_text(encoding="utf-8")
    runner_manifest = (snapshot / "assets" / "runner.json").read_text(encoding="utf-8")

    settings = adapter.config_composer.compose(ctx)

    assert settings.exists()
    assert (ctx.run_dir / "CODEBUDDY.md").exists()
    assert (ctx.run_dir / ".codebuddy" / "mcp.json").read_text(encoding="utf-8") == '{\n  "mcpServers": {}\n}\n'
    assert (snapshot / "SKILL.md").read_text(encoding="utf-8") == skill_markdown
    assert (snapshot / "assets" / "runner.json").read_text(encoding="utf-8") == runner_manifest


def test_codebuddy_parser_requires_non_error_terminal_result() -> None:
    parser = CodeBuddyStreamParser(SimpleNamespace())
    success = parser.parse('{"type":"system.init","session_id":"one"}\n{"type":"result","subtype":"success","structured_output":{"ok":true}}\n')
    error = parser.parse('{"type":"result","subtype":"error","is_error":true}\n')
    missing = parser.parse('{"type":"assistant.text","text":"partial"}\n')
    assert success["turn_result"]["outcome"] == "final"
    assert error["turn_result"]["outcome"] == "error"
    assert missing["turn_result"]["failure_reason"] == "CODEBUDDY_MISSING_TERMINAL_RESULT"


def test_codebuddy_parser_emits_high_confidence_auth_signal() -> None:
    parser = CodeBuddyStreamParser(CodeBuddyExecutionAdapter())
    runtime = parser.parse_runtime_stream(
        stdout_raw=b'{"type":"result","subtype":"error","result":"401 Unauthorized login required"}\n',
        stderr_raw=b"",
    )
    assert runtime["auth_signal"]["confidence"] == "high"


def test_codebuddy_parser_detects_auth_signal_from_stderr() -> None:
    parser = CodeBuddyStreamParser(CodeBuddyExecutionAdapter())
    runtime = parser.parse_runtime_stream(
        stdout_raw=b"",
        stderr_raw=b"401 Unauthorized: login required",
    )
    assert runtime["auth_signal"]["required"] is True
    assert runtime["auth_signal"]["confidence"] == "high"


@pytest.mark.parametrize(
    ("state", "reason_code"),
    [
        ("missing", "CODEBUDDY_CREDENTIAL_MISSING"),
        ("expired", "CODEBUDDY_CREDENTIAL_EXPIRED"),
    ],
)
def test_codebuddy_managed_env_requires_present_credential(
    tmp_path: Path,
    monkeypatch,
    state: str,
    reason_code: str,
) -> None:
    adapter = CodeBuddyExecutionAdapter()
    monkeypatch.setattr(
        "server.engines.codebuddy.managed_environment.codebuddy_credential_store.project_status",
        lambda _provider_id: SimpleNamespace(credential_state=state),
    )
    monkeypatch.setattr(
        "server.engines.codebuddy.managed_environment.codebuddy_credential_store.get",
        lambda _provider_id: None if state == "missing" else SimpleNamespace(token="expired", user_id="user"),
    )

    with pytest.raises(AdapterAuthenticationRequired) as exc_info:
        adapter.build_execution_env(
            {"CODEBUDDY_AUTH_TOKEN": "inherited"},
            _ctx(tmp_path),
            tmp_path / "settings.json",
        )

    assert exc_info.value.signal["reason_code"] == reason_code
    assert exc_info.value.signal["provider_id"] == "codebuddy-cn"


@pytest.mark.asyncio
async def test_codebuddy_missing_credential_returns_auth_required_without_process_launch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    adapter = CodeBuddyExecutionAdapter()
    ctx = _ctx(tmp_path)
    monkeypatch.setattr(
        adapter.agent_manager,
        "resolve_engine_command",
        lambda _engine: Path("/managed/codebuddy"),
    )
    monkeypatch.setattr(
        "server.engines.codebuddy.managed_environment.codebuddy_credential_store.project_status",
        lambda _provider_id: SimpleNamespace(credential_state="missing"),
    )
    monkeypatch.setattr(
        "server.engines.codebuddy.managed_environment.codebuddy_credential_store.get",
        lambda _provider_id: None,
    )
    spawn_calls: list[object] = []

    async def _unexpected_spawn(*args, **kwargs):  # noqa: ANN002, ANN003
        spawn_calls.append((args, kwargs))
        raise AssertionError("CodeBuddy CLI must not start before authentication")

    monkeypatch.setattr(adapter, "_create_subprocess", _unexpected_spawn)

    result = await adapter._execute_process(
        "prompt",
        ctx.run_dir,
        ctx.skill,
        dict(ctx.options),
        config_path=ctx.run_dir / ".codebuddy" / "settings.json",
    )

    assert result.failure_reason == "AUTH_REQUIRED"
    assert result.raw_stdout == result.raw_stderr == ""
    assert result.auth_signal_snapshot == {
        "required": True,
        "confidence": "high",
        "subcategory": "oauth_reauth",
        "provider_id": "codebuddy-cn",
        "reason_code": "CODEBUDDY_CREDENTIAL_MISSING",
        "matched_pattern_id": "codebuddy_credential_missing",
    }
    assert spawn_calls == []


def test_codebuddy_live_and_batch_share_terminal_framer() -> None:
    parser = CodeBuddyStreamParser(SimpleNamespace())
    live = parser.start_live_session()
    init_emissions = live.feed(
        stream="stdout",
        text='{"type":"system.init","session_id":"one"}\n',
        byte_from=0,
        byte_to=40,
    )
    result_emissions = live.feed(
        stream="stdout",
        text='{"type":"result","subtype":"success","result":"ok"}\n',
        byte_from=40,
        byte_to=96,
    )
    finish_emissions = live.finish(exit_code=0, failure_reason=None)

    assert any(item.get("kind") == "run_handle" for item in init_emissions)
    assert any(item.get("kind") == "turn_marker" and item.get("marker") == "start" for item in init_emissions)
    assert any(item.get("kind") == "assistant_message" for item in result_emissions)
    assert any(item.get("kind") == "turn_completed" for item in result_emissions)
    assert finish_emissions == []


def test_codebuddy_live_parser_does_not_mask_output_capture_failure() -> None:
    live = CodeBuddyStreamParser(SimpleNamespace()).start_live_session()

    emissions = live.finish(exit_code=-15, failure_reason="OUTPUT_REDACTION_FAILED")

    assert not any(
        item.get("kind") == "turn_marker"
        and item.get("marker") == "failed"
        and item.get("details", {}).get("code") == "CODEBUDDY_MISSING_TERMINAL_RESULT"
        for item in emissions
    )


def test_codebuddy_framer_repairs_physical_newline_inside_json_string() -> None:
    frames = CodeBuddyStreamFramer().feed(
        '{"type":"assistant.text","text":"first line\nsecond line"}\n'
    )
    assert len(frames) == 1
    assert frames[0].payload == {
        "type": "assistant.text",
        "text": "first line\nsecond line",
    }


def test_codebuddy_framer_resynchronizes_after_unterminated_row() -> None:
    framer = CodeBuddyStreamFramer()
    frames = framer.feed(
        '{"type":"assistant.text","text":"unterminated\n'
        '{"type":"result","subtype":"success","result":"ok"}\n'
    ) + framer.finish()

    assert frames[0].diagnostic == "CODEBUDDY_FRAME_UNTERMINATED"
    assert frames[1].payload == {"type": "result", "subtype": "success", "result": "ok"}


@pytest.mark.parametrize("transport", ["stdio", "http", "sse"])
def test_codebuddy_mcp_config_is_strict_and_transport_typed(transport: str) -> None:
    definition = McpServerDefinition(id="demo", activation="default", effective_engines=("codebuddy",), scope="run-local", transport=transport, command="demo" if transport == "stdio" else None, url="https://mcp.invalid" if transport != "stdio" else None)
    payload = render_mcp_config("codebuddy", (ResolvedMcpServer(definition=definition, scope="run-local"),))
    assert payload["mcpServers"]["demo"]["type"] == transport


def test_codebuddy_reserved_runtime_env_is_rejected_before_model_lookup() -> None:
    with pytest.raises(ValueError) as exc_info:
        validate_runtime_and_model_options(engine="codebuddy", model=None, provider_id="codebuddy-cn", runtime_options={"env": {"CODEBUDDY_AUTH_TOKEN": "token"}})
    assert getattr(exc_info.value, "detail")["code"] == "ENGINE_RUNTIME_ENV_RESERVED"
    assert getattr(exc_info.value, "detail")["field"].endswith("CODEBUDDY_AUTH_TOKEN")


def test_codebuddy_profile_declares_managed_environment_keys() -> None:
    adapter = CodeBuddyExecutionAdapter()
    assert set(adapter.profile.launch.managed_env_keys) == {
        "CODEBUDDY_AUTH_TOKEN",
        "CODEBUDDY_API_KEY",
        "CODEBUDDY_INTERNET_ENVIRONMENT",
        "CODEBUDDY_BASE_URL",
        "CODEBUDDY_CONFIG_DIR",
    }
    assert adapter.profile.model_catalog.mode == "manifest"
    assert adapter.profile.resolve_manifest_path() == (
        Path("server/engines/codebuddy/models/manifest.json").resolve()
    )


def test_codebuddy_resume_rejects_provider_mismatch(tmp_path: Path, monkeypatch) -> None:
    adapter = CodeBuddyExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/managed/codebuddy"))
    ctx = _ctx(tmp_path, {"provider_id": "codebuddy-global"})
    handle = EngineSessionHandle(
        engine="codebuddy",
        handle_type=EngineSessionHandleType.SESSION_ID,
        handle_value="session-1",
        provider_id="codebuddy-cn",
    )

    with pytest.raises(RuntimeError, match="provider mismatch"):
        adapter.command_builder.build_resume(ctx, "reply", handle)
