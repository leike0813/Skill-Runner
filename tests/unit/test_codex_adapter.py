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


def test_parse_runtime_stream_maps_turn_complete_usage_payload():
    adapter = CodexExecutionAdapter(config_manager=MagicMock())
    parsed = adapter.parse_runtime_stream(
        stdout_raw=(
            b'{"type":"turn.started"}\n'
            b'{"type":"item.completed","item":{"type":"agent_message","text":"hello"}}\n'
            b'{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":2}}\n'
        ),
        stderr_raw=b"",
        pty_raw=b"",
    )
    turn_complete_data = parsed.get("turn_complete_data")
    assert isinstance(turn_complete_data, dict)
    assert turn_complete_data.get("input_tokens") == 10
    assert turn_complete_data.get("output_tokens") == 2


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
            "interactive_auto_reply": False,
            "interactive_reply_timeout_sec": 1200,
            "__resume_session_handle": {"handle_value": "th_1"},
            "codex_config": {
                "sandbox_mode": "workspace-write",
                "interactive_reply_timeout_sec": 999,
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
    assert "interactive_auto_reply" not in passed_overrides
    assert "interactive_reply_timeout_sec" not in passed_overrides


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


def test_construct_config_prefers_runner_declared_skill_config(tmp_path):
    config_manager = MagicMock()
    config_path = tmp_path / ".codex" / "config.toml"
    config_manager.config_path = config_path
    config_manager.generate_profile_settings.return_value = {"model": "gpt-5.2-codex"}
    adapter = CodexExecutionAdapter(config_manager=config_manager)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    custom_dir = skill_dir / "custom"
    custom_dir.mkdir(parents=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    (custom_dir / "codex_config.toml").write_text("model = 'declared'\n", encoding="utf-8")
    (assets_dir / "codex_config.toml").write_text("model = 'fallback'\n", encoding="utf-8")
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engine_configs={"codex": "custom/codex_config.toml"},
    )

    result_path = adapter._construct_config(
        skill,
        run_dir,
        options={},
    )

    assert result_path == config_path
    passed_skill_defaults, _ = config_manager.generate_profile_settings.call_args[0]
    assert passed_skill_defaults["model"] == "declared"


def test_setup_environment_validates_run_folder_contract(tmp_path):
    adapter = CodexExecutionAdapter(config_manager=MagicMock())
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
    config_path = run_dir / ".codex" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("", encoding="utf-8")

    target = adapter._setup_environment(skill, run_dir, config_path, options={})

    assert target == skill_dir.resolve()


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
async def test_run_interactive_reply_rebuilds_config_and_environment_setup(tmp_path):
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

    with patch.object(
        adapter.config_composer,
        "compose",
        autospec=True,
        return_value=run_dir / ".codex" / "config.toml",
    ) as mock_compose, \
         patch.object(
             adapter.run_folder_validator,
             "validate",
             autospec=True,
             return_value=run_dir,
         ) as mock_validate, \
         patch.object(adapter.prompt_builder, "render", autospec=True, return_value="reply prompt"), \
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

    assert mock_compose.call_count == 1
    assert mock_validate.call_count == 1


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
