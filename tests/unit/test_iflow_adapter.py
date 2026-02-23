import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.adapters.iflow_adapter import IFlowAdapter
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

    adapter = IFlowAdapter()
    options = {
        "model": "gpt-4-test",
        "verbose": True,
        "iflow_config": {"theme": "Dark"}
    }

    config_path = adapter._construct_config(skill, run_dir, options)
    assert config_path.exists()

    args = json.loads(config_path.read_text())
    assert args["modelName"] == "gpt-4-test"
    assert args["theme"] == "Dark"
    assert "verbose" not in args


def test_extract_session_handle_from_execution_info():
    adapter = IFlowAdapter()
    raw_stdout = """
<Execution Info>
{"session-id":"iflow-123"}
</Execution Info>
"""
    handle = adapter.extract_session_handle(raw_stdout, turn_index=3)
    assert handle.handle_value == "iflow-123"
    assert handle.created_at_turn == 3


def test_extract_session_handle_missing_session_id_raises():
    adapter = IFlowAdapter()
    with pytest.raises(RuntimeError, match="SESSION_RESUME_FAILED"):
        adapter.extract_session_handle("<Execution Info>{}</Execution Info>", turn_index=1)


def test_parse_runtime_stream_extracts_session_id_from_execution_info_and_cleans_message():
    adapter = IFlowAdapter()
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


def test_parse_runtime_stream_extracts_session_id_from_pty_when_stdout_missing():
    adapter = IFlowAdapter()
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


def test_parse_runtime_stream_prefers_split_stream_over_pty_duplicate():
    adapter = IFlowAdapter()
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


def test_parse_runtime_stream_uses_pty_fallback_when_split_empty():
    adapter = IFlowAdapter()
    parsed = adapter.parse_runtime_stream(
        stdout_raw=b"",
        stderr_raw=b"",
        pty_raw=b"hello from pty only\n",
    )
    assert parsed["assistant_messages"]
    assert parsed["assistant_messages"][0]["text"] == "hello from pty only"
    assert "PTY_FALLBACK_USED" in parsed["diagnostics"]


def test_parse_output_valid_ask_user_envelope():
    adapter = IFlowAdapter()
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
    adapter = IFlowAdapter()
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


@pytest.mark.asyncio
async def test_execute_resume_command_contains_resume_flag(tmp_path):
    adapter = IFlowAdapter()
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
    adapter = IFlowAdapter()
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
    adapter = IFlowAdapter()
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
