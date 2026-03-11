import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.engines.iflow.adapter.execution_adapter import IFlowExecutionAdapter
from server.models import AdapterTurnOutcome, SkillManifest


def test_construct_config_maps_model_and_merges_iflow_config(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    skill = SkillManifest(
        id="test-skill",
        path=tmp_path,
        name="Test Skill",
        description="Test",
        runtime=None,
        entrypoint={}
    )

    adapter = IFlowExecutionAdapter()
    options = {
        "model": "gpt-4-test",
        "iflow_config": {"theme": "Dark"}
    }

    config_path = adapter._construct_config(skill, run_dir, options)
    assert config_path.exists()

    args = json.loads(config_path.read_text())
    assert args["modelName"] == "gpt-4-test"
    assert args["theme"] == "Dark"


def test_construct_config_uses_engine_default_when_no_overrides(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill = SkillManifest(id="test-skill", path=tmp_path)
    adapter = IFlowExecutionAdapter()

    config_path = adapter._construct_config(skill, run_dir, options={})
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    assert payload["modelName"] == "glm-5"


def test_construct_config_skill_overrides_engine_default(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    skill_dir = tmp_path / "skill"
    skill_assets = skill_dir / "assets"
    skill_assets.mkdir(parents=True)
    (skill_assets / "iflow_settings.json").write_text(
        json.dumps({"modelName": "iflow-skill-model"}),
        encoding="utf-8",
    )
    skill = SkillManifest(id="test-skill", path=skill_dir)
    adapter = IFlowExecutionAdapter()

    config_path = adapter._construct_config(skill, run_dir, options={})
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    assert payload["modelName"] == "iflow-skill-model"


def test_construct_config_prefers_runner_declared_skill_config(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    custom_dir = skill_dir / "custom"
    custom_dir.mkdir(parents=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    (custom_dir / "iflow_settings.json").write_text(
        json.dumps({"modelName": "iflow-declared-model"}),
        encoding="utf-8",
    )
    (assets_dir / "iflow_settings.json").write_text(
        json.dumps({"modelName": "iflow-fallback-model"}),
        encoding="utf-8",
    )
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engine_configs={"iflow": "custom/iflow_settings.json"},
    )
    adapter = IFlowExecutionAdapter()

    config_path = adapter._construct_config(skill, run_dir, options={})
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    assert payload["modelName"] == "iflow-declared-model"


def test_extract_session_handle_from_execution_info():
    adapter = IFlowExecutionAdapter()
    raw_stdout = """
<Execution Info>
{"session-id":"iflow-123"}
</Execution Info>
"""
    handle = adapter.extract_session_handle(raw_stdout, turn_index=3)
    assert handle.handle_value == "iflow-123"
    assert handle.created_at_turn == 3


def test_extract_session_handle_missing_session_id_raises():
    adapter = IFlowExecutionAdapter()
    with pytest.raises(RuntimeError, match="SESSION_RESUME_FAILED"):
        adapter.extract_session_handle("<Execution Info>{}</Execution Info>", turn_index=1)


def test_parse_runtime_stream_extracts_session_id_from_execution_info_and_cleans_message():
    adapter = IFlowExecutionAdapter()
    parsed = adapter.parse_runtime_stream(
        stdout_raw=(
            b"hello from iflow\n"
            b"<Execution Info>\n"
            b"{\"session-id\":\"iflow-xyz\",\"assistantRounds\":1}\n"
            b"</Execution Info>\n"
        ),
        stderr_raw=b"",
        pty_raw=b"",
    )
    assert parsed["session_id"] == "iflow-xyz"
    assert parsed["assistant_messages"]
    assert parsed["assistant_messages"][0]["text"] == "hello from iflow"
    run_handle = parsed.get("run_handle")
    assert isinstance(run_handle, dict)
    assert run_handle.get("handle_id") == "iflow-xyz"
    turn_complete_data = parsed.get("turn_complete_data")
    assert isinstance(turn_complete_data, dict)
    assert turn_complete_data.get("assistantRounds") == 1


def test_parse_runtime_stream_extracts_session_id_from_pty_when_stdout_missing():
    adapter = IFlowExecutionAdapter()
    parsed = adapter.parse_runtime_stream(
        stdout_raw=b"",
        stderr_raw=b"",
        pty_raw=(
            b"<Execution Info>\n"
            b"{\"session-id\":\"iflow-from-pty\"}\n"
            b"</Execution Info>\n"
        ),
    )
    assert parsed["session_id"] == "iflow-from-pty"
    run_handle = parsed.get("run_handle")
    assert isinstance(run_handle, dict)
    assert run_handle.get("handle_id") == "iflow-from-pty"


def test_parse_runtime_stream_prefers_split_stream_over_pty_duplicate():
    adapter = IFlowExecutionAdapter()
    parsed = adapter.parse_runtime_stream(
        stdout_raw=(
            b"hello from iflow\n"
            b"<Execution Info>\n"
            b"{\"session-id\":\"iflow-main\"}\n"
            b"</Execution Info>\n"
        ),
        stderr_raw=b"",
        pty_raw=(
            b"hello from iflow\n"
            b"<Execution Info>\n"
            b"{\"session-id\":\"iflow-main\"}\n"
            b"</Execution Info>\n"
        ),
    )
    assert parsed["assistant_messages"]
    assert parsed["assistant_messages"][0]["text"] == "hello from iflow"
    assert "PTY_FALLBACK_USED" not in parsed["diagnostics"]
    run_handle = parsed.get("run_handle")
    assert isinstance(run_handle, dict)
    assert run_handle.get("handle_id") == "iflow-main"


def test_parse_runtime_stream_uses_pty_fallback_when_split_empty():
    adapter = IFlowExecutionAdapter()
    parsed = adapter.parse_runtime_stream(
        stdout_raw=b"",
        stderr_raw=b"",
        pty_raw=b"hello from pty only\n",
    )
    assert parsed["assistant_messages"]
    assert parsed["assistant_messages"][0]["text"] == "hello from pty only"
    assert "PTY_FALLBACK_USED" in parsed["diagnostics"]


def test_parse_runtime_stream_keeps_latest_round_text():
    adapter = IFlowExecutionAdapter()
    parsed = adapter.parse_runtime_stream(
        stdout_raw=(
            b"old round output\n"
            b"<Execution Info>\n"
            b'{"session-id":"iflow-r1"}\n'
            b"</Execution Info>\n"
            b"latest round output\n"
            b"<Execution Info>\n"
            b'{"session-id":"iflow-r2"}\n'
            b"</Execution Info>\n"
        ),
        stderr_raw=b"",
        pty_raw=b"",
    )
    assert parsed["assistant_messages"]
    assert [msg["text"] for msg in parsed["assistant_messages"]] == ["latest round output"]


def test_parse_runtime_stream_channel_drift_correction_diagnostics():
    adapter = IFlowExecutionAdapter()
    parsed = adapter.parse_runtime_stream(
        stdout_raw=(
            b"<Execution Info>\n"
            b'{"session-id":"iflow-drift","assistantRounds":2}\n'
            b"</Execution Info>\n"
        ),
        stderr_raw=b"message from stderr\n",
        pty_raw=b"",
    )
    assert parsed["assistant_messages"]
    assert parsed["assistant_messages"][0]["text"] == "message from stderr"
    diagnostics = parsed.get("diagnostics", [])
    assert "IFLOW_CHANNEL_DRIFT_OBSERVED" in diagnostics
    assert "IFLOW_EXECUTION_INFO_CHANNEL_DRIFT_CORRECTED" in diagnostics
    assert "IFLOW_MESSAGE_CHANNEL_DRIFT_CORRECTED" in diagnostics


def test_live_session_assistant_message_keeps_raw_ref():
    adapter = IFlowExecutionAdapter()
    session = adapter.stream_parser.start_live_session()
    payload = "hello from iflow live\n"
    encoded = payload.encode("utf-8")
    session.feed(stream="stdout", text=payload, byte_from=0, byte_to=len(encoded))
    emissions = session.finish(exit_code=0, failure_reason=None)

    assistant = next(
        (item for item in emissions if isinstance(item, dict) and item.get("kind") == "assistant_message"),
        None,
    )
    assert isinstance(assistant, dict)
    raw_ref = assistant.get("raw_ref")
    assert isinstance(raw_ref, dict)
    assert raw_ref.get("stream") == "stdout"
    assert int(raw_ref.get("byte_from", -1)) == 0
    assert int(raw_ref.get("byte_to", -1)) == len(encoded)


def test_parse_runtime_stream_keeps_resume_stderr_line_as_raw_when_execution_info_consumed():
    adapter = IFlowExecutionAdapter()
    parsed = adapter.parse_runtime_stream(
        stdout_raw=b"hello from iflow\n",
        stderr_raw=(
            b"\n"
            b"\xe2\x84\xb9\xef\xb8\x8f  Resuming session session-4062bdd2-16d0-494a-8ce9-fff6f2142e69 "
            b"(10 messages loaded)\n"
            b"<Execution Info>\n"
            b'{"session-id":"iflow-resume","assistantRounds":3}\n'
            b"</Execution Info>\n"
        ),
        pty_raw=b"",
    )

    raw_rows = parsed.get("raw_rows", [])
    assert any(
        isinstance(row, dict)
        and str(row.get("stream")) == "stderr"
        and "Resuming session" in str(row.get("line", ""))
        for row in raw_rows
    )
    assert not any(
        isinstance(row, dict)
        and str(row.get("stream")) == "stderr"
        and "<Execution Info>" in str(row.get("line", ""))
        for row in raw_rows
    )


def test_parse_output_valid_ask_user_envelope():
    adapter = IFlowExecutionAdapter()
    raw = json.dumps(
        {
            "outcome": "ask_user",
            "interaction": {
                "interaction_id": 11,
                "kind": "choose_one",
                "prompt": "pick one",
                "options": [{"label": "A", "value": "a"}],
            },
        }
    )
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.ASK_USER
    assert result.interaction is not None
    assert result.interaction.interaction_id == 11


def test_parse_output_invalid_ask_user_payload_returns_error():
    adapter = IFlowExecutionAdapter()
    raw = json.dumps(
        {
            "outcome": "ask_user",
            "interaction": {
                "prompt": "missing interaction id",
            },
        }
    )
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.ERROR


def test_setup_environment_validates_run_folder_contract(tmp_path):
    adapter = IFlowExecutionAdapter()
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": "test-skill",
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
        id="test-skill",
        path=skill_dir,
        schemas={"output": "assets/output.schema.json"},
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    config_path = run_dir / ".iflow" / "settings.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{}", encoding="utf-8")

    target = adapter._setup_environment(skill, run_dir, config_path, options={})

    assert target == skill_dir.resolve()


@pytest.mark.asyncio
async def test_execute_resume_command_contains_resume_flag(tmp_path):
    adapter = IFlowExecutionAdapter()
    adapter.agent_manager.resolve_engine_command = lambda _engine: Path("/usr/bin/iflow")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "logs").mkdir()
    skill = SkillManifest(id="test-skill", path=tmp_path)

    mock_proc = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stderr = MagicMock()
    mock_proc.stdout.read = AsyncMock(side_effect=[b""])
    mock_proc.stderr.read = AsyncMock(side_effect=[b""])
    mock_proc.wait = AsyncMock()
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_proc
        await adapter._execute_process(
            "resume prompt",
            run_dir,
            skill,
            options={
                "__resume_session_handle": {
                    "engine": "iflow",
                    "handle_type": "session_id",
                    "handle_value": "iflow-session",
                    "created_at_turn": 1,
                }
            },
        )
        args, _ = mock_exec.call_args
        assert "--resume" in args
        assert "iflow-session" in args
        assert "--yolo" in args
        assert "--thinking" in args


@pytest.mark.asyncio
async def test_execute_interactive_command_includes_yolo_and_thinking(tmp_path):
    adapter = IFlowExecutionAdapter()
    adapter.agent_manager.resolve_engine_command = lambda _engine: Path("/usr/bin/iflow")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "logs").mkdir()
    skill = SkillManifest(id="test-skill", path=tmp_path)

    mock_proc = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stderr = MagicMock()
    mock_proc.stdout.read = AsyncMock(side_effect=[b""])
    mock_proc.stderr.read = AsyncMock(side_effect=[b""])
    mock_proc.wait = AsyncMock()
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_proc
        await adapter._execute_process(
            "interactive prompt",
            run_dir,
            skill,
            options={"execution_mode": "interactive"},
        )
        args, _ = mock_exec.call_args
        assert "--yolo" in args
        assert "--thinking" in args


@pytest.mark.asyncio
async def test_execute_auto_command_includes_yolo_and_thinking(tmp_path):
    adapter = IFlowExecutionAdapter()
    adapter.agent_manager.resolve_engine_command = lambda _engine: Path("/usr/bin/iflow")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "logs").mkdir()
    skill = SkillManifest(id="test-skill", path=tmp_path)

    mock_proc = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stderr = MagicMock()
    mock_proc.stdout.read = AsyncMock(side_effect=[b""])
    mock_proc.stderr.read = AsyncMock(side_effect=[b""])
    mock_proc.wait = AsyncMock()
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_proc
        await adapter._execute_process(
            "auto prompt",
            run_dir,
            skill,
            options={"execution_mode": "auto"},
        )
        args, _ = mock_exec.call_args
        assert "--yolo" in args
        assert "--thinking" in args
