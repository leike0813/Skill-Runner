from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.engines.kilo.adapter.execution_adapter import KiloExecutionAdapter
from server.models import EngineSessionHandle, EngineSessionHandleType, SkillManifest
from server.models.common import AdapterTurnOutcome
from server.runtime.adapter.contracts import AdapterExecutionContext


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_kilo_command_builder_start_and_resume(monkeypatch) -> None:
    adapter = KiloExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/kilo"))
    run_dir = Path("/tmp/kilo-run")
    ctx = AdapterExecutionContext(
        skill=SkillManifest(id="test-skill"),
        run_dir=run_dir,
        input_data={},
        options={"runtime_model": "kilo/kilo-auto/free"},
    )

    start = adapter.build_start_command(
        ctx=ctx,
        prompt="hello",
        options={"runtime_model": "kilo/kilo-auto/free"},
    )
    resume = adapter.command_builder.build_resume_with_options(
        prompt="again",
        options={"runtime_model": "kilo/kilo-auto/free"},
        ctx=ctx,
        session_handle=EngineSessionHandle(
            engine="kilo",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="session-123",
        ),
    )

    assert start == [
        "/usr/bin/kilo",
        "run",
        "--dir",
        str(run_dir),
        "--format",
        "json",
        "--auto",
        "--thinking",
        "--model",
        "kilo/kilo-auto/free",
        "hello",
    ]
    assert resume == [
        "/usr/bin/kilo",
        "run",
        "--dir",
        str(run_dir),
        "--format",
        "json",
        "--auto",
        "--thinking",
        "--session",
        "session-123",
        "--model",
        "kilo/kilo-auto/free",
        "again",
    ]


def test_kilo_execution_env_sets_config_path(tmp_path: Path) -> None:
    adapter = KiloExecutionAdapter()
    ctx = AdapterExecutionContext(
        skill=SkillManifest(id="test-skill"),
        run_dir=tmp_path,
        input_data={},
        options={},
    )
    config_path = tmp_path / ".kilo" / "kilo.jsonc"

    env = adapter.build_execution_env({}, ctx, config_path)

    assert env["KILO_CONFIG"] == str(config_path)


def test_kilo_config_composer_writes_project_level_jsonc_and_applies_layers(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    run_skill_dir = run_dir / ".kilo" / "skills" / "test-skill"
    run_skill_dir.mkdir(parents=True)
    (run_skill_dir / "SKILL.md").write_text("# test-skill\n", encoding="utf-8")
    skill_dir = tmp_path / "skill"
    skill_assets = skill_dir / "assets"
    skill_assets.mkdir(parents=True)
    (skill_assets / "kilo_config.json").write_text(
        json.dumps(
            {
                "model": "skill/model",
                "nested": {"source": "skill", "keep": True},
            }
        ),
        encoding="utf-8",
    )

    adapter = KiloExecutionAdapter()
    ctx = AdapterExecutionContext(
        skill=SkillManifest(id="test-skill", path=skill_dir),
        run_dir=run_dir,
        input_data={},
        options={
            "runtime_model": "kilo/kilo-auto/free",
            "kilo_config": {
                "nested": {"source": "runtime"},
                "skills": {"paths": ["/external/kilo/skills"]},
            },
        },
    )

    assert adapter.config_composer is not None
    config_path = adapter.config_composer.compose(ctx)
    payload = _read_json(config_path)

    assert config_path == run_dir / ".kilo" / "kilo.jsonc"
    assert payload["$schema"] == "https://app.kilo.ai/config.json"
    assert payload["model"] == "kilo/kilo-auto/free"
    assert payload["nested"] == {"source": "runtime", "keep": True}
    assert payload["skills"]["paths"] == [
        "/external/kilo/skills",
        str((run_dir / ".kilo" / "skills").resolve()),
    ]


def test_kilo_config_composer_allows_provider_root(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    adapter = KiloExecutionAdapter()
    ctx = AdapterExecutionContext(
        skill=SkillManifest(id="test-skill"),
        run_dir=run_dir,
        input_data={},
        options={
            "kilo_config": {
                "provider": {
                    "openai-compatible": {
                        "name": "Local Provider",
                        "options": {
                            "apiKey": "{env:MY_PROVIDER_API_KEY}",
                            "baseURL": "https://example.invalid/v1",
                        },
                        "models": {
                            "my-model": {
                                "name": "My Model",
                                "tool_call": True,
                            }
                        },
                    }
                },
                "model": "openai-compatible/my-model",
            }
        },
    )

    assert adapter.config_composer is not None
    config_path = adapter.config_composer.compose(ctx)
    payload = _read_json(config_path)

    assert payload["provider"]["openai-compatible"]["models"]["my-model"]["tool_call"] is True
    assert payload["model"] == "openai-compatible/my-model"


def test_kilo_config_composer_rejects_user_mcp_root(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    adapter = KiloExecutionAdapter()
    ctx = AdapterExecutionContext(
        skill=SkillManifest(id="test-skill"),
        run_dir=run_dir,
        input_data={},
        options={"kilo_config": {"mcp": {}}},
    )

    assert adapter.config_composer is not None
    with pytest.raises(ValueError):
        adapter.config_composer.compose(ctx)


def test_kilo_parse_runtime_stream_extracts_text_session_tokens_and_cost() -> None:
    adapter = KiloExecutionAdapter()
    stdout = (
        b'{"type":"step_start","sessionID":"session-kilo","part":{"type":"step-start"}}\n'
        b'{"type":"text","sessionID":"session-kilo","part":{"type":"text","text":"hello"}}\n'
        b'{"type":"step_finish","sessionID":"session-kilo","part":{"type":"step-finish","tokens":{"input":1,"output":2},"cost":0}}\n'
    )

    parsed = adapter.parse_runtime_stream(stdout_raw=stdout, stderr_raw=b"")

    assert parsed["parser"] == "kilo_jsonl"
    assert parsed["session_id"] == "session-kilo"
    assert parsed["run_handle"]["handle_id"] == "session-kilo"
    assert parsed["assistant_messages"][0]["text"] == "hello"
    assert parsed["turn_started"] is True
    assert parsed["turn_completed"] is True
    assert parsed["turn_complete_data"]["tokens"] == {"input": 1, "output": 2}
    assert parsed["turn_complete_data"]["cost"] == 0


def test_kilo_parse_runtime_stream_extracts_opencode_family_process_events() -> None:
    adapter = KiloExecutionAdapter()
    stdout = (
        b'{"type":"step_start","sessionID":"session-kilo","part":{"type":"step-start"}}\n'
        b'{"type":"tool_use","sessionID":"session-kilo","part":{"type":"tool","id":"p1","tool":"bash","state":{"status":"completed","input":{"command":"echo hi"},"output":"hi"}}}\n'
        b'{"type":"step_finish","sessionID":"session-kilo","part":{"type":"step-finish","reason":"tool-calls","tokens":{"input":3,"output":4,"reasoning":5},"cost":0}}\n'
        b'{"type":"step_start","sessionID":"session-kilo","part":{"type":"step-start"}}\n'
        b'{"type":"tool_use","sessionID":"session-kilo","part":{"type":"tool","id":"p2","tool":"webfetch","state":{"status":"completed","input":{"url":"https://example.invalid","format":"text"},"output":"example"}}}\n'
        b'{"type":"text","sessionID":"session-kilo","part":{"type":"text","text":"done"}}\n'
        b'{"type":"step_finish","sessionID":"session-kilo","part":{"type":"step-finish","tokens":{"input":1,"output":2,"reasoning":7},"cost":0}}\n'
    )

    parsed = adapter.parse_runtime_stream(stdout_raw=stdout, stderr_raw=b"")

    process_events = parsed["process_events"]
    assert [event["process_type"] for event in process_events] == [
        "command_execution",
        "tool_call",
    ]
    assert process_events[0]["summary"] == "echo hi"
    assert process_events[0]["text"] == "hi"
    assert process_events[1]["summary"] == "webfetch"
    assert parsed["assistant_messages"] == [
        {
            "text": "done",
            "raw_ref": parsed["assistant_messages"][0]["raw_ref"],
        }
    ]
    assert parsed["turn_complete_data"]["tokens"]["reasoning"] == 7


def test_kilo_parse_runtime_stream_extracts_reasoning_process_event() -> None:
    adapter = KiloExecutionAdapter()
    stdout = (
        b'{"type":"step_start","sessionID":"session-kilo","part":{"type":"step-start"}}\n'
        b'{"type":"reasoning","sessionID":"session-kilo","part":{"type":"reasoning","id":"r1","text":"draft plan"}}\n'
        b'{"type":"text","sessionID":"session-kilo","part":{"type":"text","text":"final answer"}}\n'
        b'{"type":"step_finish","sessionID":"session-kilo","part":{"type":"step-finish","tokens":{"input":1,"output":2,"reasoning":3},"cost":0}}\n'
    )

    parsed = adapter.parse_runtime_stream(stdout_raw=stdout, stderr_raw=b"")

    process_events = parsed["process_events"]
    assert [event["process_type"] for event in process_events] == ["reasoning"]
    assert process_events[0]["message_id"] == "r1"
    assert process_events[0]["text"] == "draft plan"
    assert parsed["assistant_messages"][0]["text"] == "final answer"
    assert parsed["turn_complete_data"]["tokens"]["reasoning"] == 3


def test_kilo_live_session_emits_process_events() -> None:
    adapter = KiloExecutionAdapter()
    session = adapter.stream_parser.start_live_session()

    emissions = session.feed(
        stream="stdout",
        text=(
            '{"type":"tool_use","sessionID":"session-kilo","part":{"type":"tool","id":"p1",'
            '"tool":"bash","state":{"status":"completed","input":{"command":"pwd"},"output":"/tmp/run"}}}\n'
        ),
        byte_from=0,
        byte_to=160,
    )

    process = next(item for item in emissions if item["kind"] == "process_event")
    assert process["process_type"] == "command_execution"
    assert process["summary"] == "pwd"
    assert process["text"] == "/tmp/run"


def test_kilo_live_session_emits_reasoning_process_event() -> None:
    adapter = KiloExecutionAdapter()
    session = adapter.stream_parser.start_live_session()

    emissions = session.feed(
        stream="stdout",
        text='{"type":"reasoning","sessionID":"session-kilo","part":{"type":"reasoning","id":"r1","text":"draft plan"}}\n',
        byte_from=0,
        byte_to=108,
    )

    process = next(item for item in emissions if item["kind"] == "process_event")
    assert process["process_type"] == "reasoning"
    assert process["message_id"] == "r1"
    assert process["text"] == "draft plan"


def test_kilo_legacy_parse_success_uses_final_turn_outcome() -> None:
    adapter = KiloExecutionAdapter()
    stdout = (
        '{"type":"step_start","sessionID":"session-kilo","part":{"type":"step-start"}}\n'
        '{"type":"text","sessionID":"session-kilo","part":{"type":"text","text":"hello"}}\n'
        '{"type":"step_finish","sessionID":"session-kilo","part":{"type":"step-finish","tokens":{"input":1,"output":2},"cost":0}}\n'
    )

    parsed = adapter.stream_parser.parse(stdout)

    assert parsed["turn_result"]["outcome"] == AdapterTurnOutcome.FINAL.value
    assert parsed["structured_payload"]["response"] == "hello"
    assert parsed["structured_payload"]["session_id"] == "session-kilo"


def test_kilo_error_jsonl_marks_failed_and_auth_required_even_without_nonzero_exit() -> None:
    adapter = KiloExecutionAdapter()
    stdout = (
        b'{"type":"error","sessionID":"session-kilo","error":{"name":"APIError","data":{"message":"You need to sign in to use this model.","statusCode":401,"responseBody":"{\\"error\\":{\\"type\\":\\"PAID_MODEL_AUTH_REQUIRED\\"}}"}}}\n'
    )

    runtime_parsed = adapter.parse_runtime_stream(stdout_raw=stdout, stderr_raw=b"")
    parsed = adapter.stream_parser.parse(stdout.decode("utf-8"))

    assert runtime_parsed["turn_failed"] is True
    assert runtime_parsed["auth_signal"]["reason_code"] == "KILO_PAID_MODEL_AUTH_REQUIRED"
    assert parsed["turn_result"]["outcome"] == "error"
    assert parsed["turn_result"]["failure_reason"] == "KILO_RUNTIME_ERROR"
