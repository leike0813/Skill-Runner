import json
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import pytest
from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.models import AdapterTurnOutcome, EngineSessionHandleType, SkillManifest


@pytest.mark.asyncio
async def test_execute_constructs_correct_command(tmp_path):
    adapter = CodexExecutionAdapter(config_manager=MagicMock())
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
    adapter = CodexExecutionAdapter(config_manager=MagicMock())
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
    adapter = CodexExecutionAdapter(config_manager=MagicMock())
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
    adapter = CodexExecutionAdapter(config_manager=MagicMock())
    raw_stdout = '\n{"type":"thread.started","thread_id":"th_123"}\n{"type":"item.completed"}\n'
    handle = adapter.extract_session_handle(raw_stdout, turn_index=2)
    assert handle.handle_type == EngineSessionHandleType.SESSION_ID
    assert handle.handle_value == "th_123"
    assert handle.created_at_turn == 2


def test_extract_session_handle_missing_thread_started_raises():
    adapter = CodexExecutionAdapter(config_manager=MagicMock())
    raw_stdout = '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}'
    with pytest.raises(RuntimeError, match="SESSION_RESUME_FAILED"):
        adapter.extract_session_handle(raw_stdout, turn_index=1)


def test_parse_runtime_stream_keeps_latest_turn_only():
    adapter = CodexExecutionAdapter(config_manager=MagicMock())
    parsed = adapter.parse_runtime_stream(
        stdout_raw=(
            b'{"type":"turn.started","turn_id":"turn-1"}\n'
            b'{"type":"item.completed","item":{"type":"agent_message","text":"old turn"}}\n'
            b'{"type":"turn.completed","turn_id":"turn-1"}\n'
            b'{"type":"turn.started","turn_id":"turn-2"}\n'
            b'{"type":"item.completed","item":{"type":"agent_message","text":"latest turn"}}\n'
            b'{"type":"turn.completed","turn_id":"turn-2"}\n'
        ),
        stderr_raw=b"",
        pty_raw=b"",
    )
    assert parsed["assistant_messages"]
    assert [msg["text"] for msg in parsed["assistant_messages"]] == ["latest turn"]


def test_construct_config_excludes_runtime_interactive_options(tmp_path):
    config_manager = MagicMock()
    config_path = tmp_path / ".codex" / "config.toml"
    config_manager.config_path = config_path
    config_manager.generate_profile_settings.return_value = {"model": "gpt-5.2-codex"}
    adapter = CodexExecutionAdapter(config_manager=config_manager)
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


def test_construct_config_allows_harness_profile_override(tmp_path):
    config_manager = MagicMock()
    config_path = tmp_path / ".codex" / "config.toml"
    config_manager.config_path = config_path
    config_manager.generate_profile_settings.return_value = {"model": "gpt-5.2-codex"}
    adapter = CodexExecutionAdapter(config_manager=config_manager)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill = SkillManifest(id="test-skill", path=tmp_path)

    result_path = adapter._construct_config(
        skill,
        run_dir,
        options={
            "__codex_profile_name": "skill-runner-harness",
        },
    )

    assert result_path == config_path
    assert config_manager.profile_name == "skill-runner-harness"
    assert config_manager.generate_profile_settings.call_count == 1
    assert config_manager.update_profile.call_count == 1


def test_setup_environment_passes_output_schema_to_skill_patcher(tmp_path):
    adapter = CodexExecutionAdapter(config_manager=MagicMock())
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (skill_dir / "output.schema.json").write_text('{"type":"object"}', encoding="utf-8")
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        schemas={"output": "output.schema.json"},
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    config_path = run_dir / ".codex" / "config.toml"

    with patch(
        "server.services.skill_patcher.skill_patcher.load_output_schema",
        return_value={"type": "object"},
    ) as mock_load, patch(
        "server.services.skill_patcher.skill_patcher.patch_skill_md"
    ) as mock_patch:
        target = adapter._setup_environment(skill, run_dir, config_path, options={})

    assert target == run_dir / ".codex" / "skills" / "test-skill"
    mock_load.assert_called_once_with(
        skill_path=skill.path,
        output_schema_relpath="output.schema.json",
    )
    _, kwargs = mock_patch.call_args
    assert kwargs["execution_mode"] == "auto"
    assert kwargs["output_schema"] == {"type": "object"}


@pytest.mark.asyncio
async def test_execute_resume_command_thread_id_before_prompt(tmp_path):
    adapter = CodexExecutionAdapter(config_manager=MagicMock())
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
        assert "--full-auto" in args or "--yolo" in args
        assert "resume" in args
        assert thread_idx < prompt_idx


@pytest.mark.asyncio
async def test_run_interactive_reply_skips_config_and_environment_setup(tmp_path):
    adapter = CodexExecutionAdapter(config_manager=MagicMock())
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    skill = SkillManifest(id="test-skill", path=skill_dir)

    process_result = MagicMock()
    process_result.exit_code = 0
    process_result.raw_stdout = '{"value":"ok"}'
    process_result.raw_stderr = ""
    process_result.failure_reason = None

    with patch.object(adapter, "_construct_config", autospec=True) as mock_construct, \
         patch.object(adapter, "_setup_environment", autospec=True) as mock_setup, \
         patch.object(adapter, "_build_prompt", autospec=True, return_value="reply prompt"), \
         patch.object(adapter, "_execute_process", new=AsyncMock(return_value=process_result)):
        await adapter.run(
            skill,
            {},
            run_dir,
            options={
                "__interactive_reply_payload": {"text": "continue"},
                "__resume_session_handle": {
                    "engine": "codex",
                    "handle_type": "session_id",
                    "handle_value": "th_resume",
                    "created_at_turn": 1,
                },
            },
        )

    assert mock_construct.call_count == 0
    assert mock_setup.call_count == 0


@pytest.mark.asyncio
async def test_execute_interactive_command_includes_auto_flags(tmp_path):
    adapter = CodexExecutionAdapter(config_manager=MagicMock())
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
        assert "--full-auto" in args or "--yolo" in args
