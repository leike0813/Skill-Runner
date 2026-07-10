from pathlib import Path
from types import SimpleNamespace

import pytest

from server.engines.codebuddy.adapter.execution_adapter import CodeBuddyExecutionAdapter
from server.engines.codebuddy.adapter.stream_parser import CodeBuddyStreamParser
from server.engines.codebuddy.models.catalog_service import CodeBuddyModelCatalog
from server.models import EngineSessionHandle, EngineSessionHandleType, SkillManifest
from server.runtime.adapter.contracts import AdapterExecutionContext
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


def test_codebuddy_config_materializes_owned_workspace(tmp_path: Path) -> None:
    adapter = CodeBuddyExecutionAdapter()
    ctx = _ctx(tmp_path)
    settings = adapter.config_composer.compose(ctx)
    assert settings.exists()
    assert (ctx.run_dir / "CODEBUDDY.md").exists()
    assert (ctx.run_dir / ".codebuddy" / "mcp.json").read_text(encoding="utf-8") == '{\n  "mcpServers": {}\n}\n'
    assert (ctx.run_dir / ".codebuddy" / "skills" / "demo" / "SKILL.md").exists()


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


def test_codebuddy_live_and_batch_share_terminal_framer() -> None:
    parser = CodeBuddyStreamParser(SimpleNamespace())
    live = parser.start_live_session()
    assert live.feed(stream="stdout", text='{"type":"system.init","session_id":"one"}\n', byte_from=0, byte_to=40) == []
    assert live.feed(stream="stdout", text='{"type":"result","subtype":"success","result":"ok"}\n', byte_from=40, byte_to=96) == []
    emissions = live.finish(exit_code=0, failure_reason=None)
    assert any(item.get("kind") == "turn_completed" for item in emissions)


def test_codebuddy_catalog_qualifies_models_and_has_no_static_fallback(tmp_path: Path) -> None:
    catalog = CodeBuddyModelCatalog(cache_path=tmp_path / "catalog.json")
    assert catalog.parse_models("--model Currently supported:\n  glm-5.2  default\n", "codebuddy-global") == [{"id": "codebuddy-global/glm-5.2", "provider": "codebuddy-global", "provider_id": "codebuddy-global", "model": "glm-5.2", "display_name": "glm-5.2", "deprecated": False, "notes": "runtime_probe_cache", "supported_effort": ["default"]}]
    assert catalog.get_snapshot()["models"] == []


@pytest.mark.parametrize("transport", ["stdio", "http", "sse"])
def test_codebuddy_mcp_config_is_strict_and_transport_typed(transport: str) -> None:
    definition = McpServerDefinition(id="demo", activation="default", effective_engines=("codebuddy",), scope="run-local", transport=transport, command="demo" if transport == "stdio" else None, url="https://mcp.invalid" if transport != "stdio" else None)
    payload = render_mcp_config("codebuddy", (ResolvedMcpServer(definition=definition, scope="run-local"),))
    assert payload["mcpServers"]["demo"]["type"] == transport


def test_codebuddy_reserved_runtime_env_is_rejected_before_model_lookup() -> None:
    with pytest.raises(ValueError, match="CODEBUDDY_AUTH_TOKEN"):
        validate_runtime_and_model_options(engine="codebuddy", model=None, provider_id="codebuddy-cn", runtime_options={"env": {"CODEBUDDY_AUTH_TOKEN": "token"}})
