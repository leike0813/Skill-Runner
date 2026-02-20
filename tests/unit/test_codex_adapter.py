import json
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import pytest
from server.adapters.codex_adapter import CodexAdapter
from server.models import AdapterTurnOutcome, EngineSessionHandleType, SkillManifest


@pytest.mark.asyncio
async def test_execute_constructs_correct_command(tmp_path):
    adapter = CodexAdapter(config_manager=MagicMock())
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "logs").mkdir()

    skill = SkillManifest(id="test-skill", path=tmp_path)
    prompt = "Hello Codex"

    mock_proc = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stderr = MagicMock()
    mock_proc.stdout.read = AsyncMock(side_effect=[b""])
    mock_proc.stderr.read = AsyncMock(side_effect=[b""])
    mock_proc.wait = AsyncMock()
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_proc
        with patch.object(adapter, "_resolve_codex_command", return_value=Path("/usr/bin/codex")):
            await adapter._execute_process(prompt, run_dir, skill, options={})

        args, _ = mock_exec.call_args
        assert Path(args[0]).name.startswith("codex")
        assert args[1] == "exec"
        assert "--full-auto" in args or "--yolo" in args
        assert "--json" in args
        assert "-p" in args
        assert "skill-runner" in args
        assert prompt in args


def test_parse_output_valid_ask_user_envelope():
    adapter = CodexAdapter(config_manager=MagicMock())
    event = {
        "type": "item.completed",
        "item": {
            "type": "agent_message",
            "text": (
                '{"outcome":"ask_user","interaction":{"interaction_id":1,'
                '"kind":"choose_one","prompt":"choose one","options":[{"label":"A","value":"a"}]}}'
            ),
        },
    }
    result = adapter._parse_output(raw_stdout=json.dumps(event))
    assert result.outcome == AdapterTurnOutcome.ASK_USER
    assert result.interaction is not None
    assert result.interaction.prompt == "choose one"


def test_parse_output_invalid_ask_user_payload_returns_error():
    adapter = CodexAdapter(config_manager=MagicMock())
    event = {
        "type": "item.completed",
        "item": {
            "type": "agent_message",
            "text": '{"outcome":"ask_user","interaction":{"prompt":"missing id"}}',
        },
    }
    result = adapter._parse_output(raw_stdout=json.dumps(event))
    assert result.outcome == AdapterTurnOutcome.ERROR


def test_extract_session_handle_from_thread_started():
    adapter = CodexAdapter(config_manager=MagicMock())
    raw_stdout = '\n{"type":"thread.started","thread_id":"th_123"}\n{"type":"item.completed"}\n'
    handle = adapter.extract_session_handle(raw_stdout, turn_index=2)
    assert handle.handle_type == EngineSessionHandleType.SESSION_ID
    assert handle.handle_value == "th_123"
    assert handle.created_at_turn == 2


def test_extract_session_handle_missing_thread_started_raises():
    adapter = CodexAdapter(config_manager=MagicMock())
    raw_stdout = '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}'
    with pytest.raises(RuntimeError, match="SESSION_RESUME_FAILED"):
        adapter.extract_session_handle(raw_stdout, turn_index=1)


def test_construct_config_excludes_runtime_interactive_options(tmp_path):
    config_manager = MagicMock()
    config_path = tmp_path / ".codex" / "config.toml"
    config_manager.config_path = config_path
    config_manager.generate_profile_settings.return_value = {"model": "gpt-5.2-codex"}
    adapter = CodexAdapter(config_manager=config_manager)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill = SkillManifest(id="test-skill", path=tmp_path)

    result_path = adapter._construct_config(
        skill,
        run_dir,
        options={
            "model": "gpt-5.2-codex",
            "model_reasoning_effort": "high",
            "execution_mode": "interactive",
            "interactive_require_user_reply": True,
            "session_timeout_sec": 1200,
            "interactive_wait_timeout_sec": 10,
            "verbose": True,
            "__resume_session_handle": {"handle_value": "th_1"},
            "codex_config": {
                "sandbox_mode": "workspace-write",
                "session_timeout_sec": 999,
            },
        },
    )

    assert result_path == config_path
    assert config_manager.generate_profile_settings.call_count == 1
    _, passed_overrides = config_manager.generate_profile_settings.call_args[0]
    assert passed_overrides["model"] == "gpt-5.2-codex"
    assert passed_overrides["model_reasoning_effort"] == "high"
    assert passed_overrides["sandbox_mode"] == "workspace-write"
    assert "execution_mode" not in passed_overrides
    assert "interactive_require_user_reply" not in passed_overrides
    assert "session_timeout_sec" not in passed_overrides
    assert "interactive_wait_timeout_sec" not in passed_overrides
    assert "verbose" not in passed_overrides


@pytest.mark.asyncio
async def test_execute_resume_command_thread_id_before_prompt(tmp_path):
    adapter = CodexAdapter(config_manager=MagicMock())
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "logs").mkdir()
    skill = SkillManifest(id="test-skill", path=tmp_path)

    mock_proc = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stderr = MagicMock()
    mock_proc.wait = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.stdout.read = AsyncMock(side_effect=[b""])
    mock_proc.stderr.read = AsyncMock(side_effect=[b""])

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_proc
        with patch.object(adapter, "_resolve_codex_command", return_value=Path("/usr/bin/codex")):
            await adapter._execute_process(
                "resume prompt",
                run_dir,
                skill,
                options={
                    "__resume_session_handle": {
                        "engine": "codex",
                        "handle_type": "session_id",
                        "handle_value": "th_resume",
                        "created_at_turn": 1,
                    }
                },
            )
        args, _ = mock_exec.call_args
        thread_idx = args.index("th_resume")
        prompt_idx = args.index("resume prompt")
        assert args[1] == "exec"
        assert args[2] == "resume"
        assert thread_idx < prompt_idx


@pytest.mark.asyncio
async def test_execute_interactive_command_excludes_auto_flags(tmp_path):
    adapter = CodexAdapter(config_manager=MagicMock())
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
        with patch.object(adapter, "_resolve_codex_command", return_value=Path("/usr/bin/codex")):
            await adapter._execute_process(
                "interactive prompt",
                run_dir,
                skill,
                options={"execution_mode": "interactive"},
            )
        args, _ = mock_exec.call_args
        assert "--full-auto" not in args
        assert "--yolo" not in args
