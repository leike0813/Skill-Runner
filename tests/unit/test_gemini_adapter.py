import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from server.adapters.gemini_adapter import GeminiAdapter
from server.models import AdapterTurnOutcome, SkillManifest

@pytest.fixture
def adapter():
    adapter = GeminiAdapter()
    adapter.agent_manager.resolve_engine_command = lambda _engine: Path("/usr/bin/gemini")
    return adapter

@pytest.fixture
def mock_skill(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    
    # Create schema files
    input_schema = {
        "type": "object",
        "properties": {"input_file": {"type": "string"}},
        "required": ["input_file"]
    }
    param_schema = {
        "type": "object",
        "properties": {"divisor": {"type": "integer"}},
        "required": ["divisor"]
    }
    
    (skill_dir / "input.schema.json").write_text(json.dumps(input_schema))
    (skill_dir / "parameter.schema.json").write_text(json.dumps(param_schema))
    
    return SkillManifest(
        id="test-skill",
        path=skill_dir,
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json"
        }
    )

@pytest.mark.asyncio
async def test_run_prompt_generation_strict_files(adapter, mock_skill, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "input.json").write_text("{}")
    
    # Mock uploads
    uploads_dir = run_dir / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / "input_file").write_text("content")
    
    input_data = {
        "parameter": {"divisor": 5},
        # "input" dict in request is not used for files anymore in strict mode
    }
    
    options = {}
    
    # Create dummy template
    template_file = tmp_path / "template.j2"
    template_file.write_text(
        "input_file: {{ input.input_file }}\n"
        "divisor: {{ parameter.divisor }}"
    )
    
    from server.config import config
    old_template = config.GEMINI.DEFAULT_PROMPT_TEMPLATE
    config.defrost()
    config.GEMINI.DEFAULT_PROMPT_TEMPLATE = str(template_file)
    config.freeze()
    
    try:
        # Mock dependencies
         with patch("server.services.config_generator.config_generator.generate_config"), \
              patch("server.services.skill_patcher.skill_patcher.patch_skill_md"), \
              patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
             
            mock_proc = MagicMock()
            mock_proc.stdout = MagicMock()
            mock_proc.stderr = MagicMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[b""])
            mock_proc.stderr.read = AsyncMock(side_effect=[b""])
            mock_proc.wait = AsyncMock()
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc
            
            await adapter.run(mock_skill, input_data, run_dir, options)
            
            # Check prompt log
            prompt_path = run_dir / "logs" / "prompt.txt"
            assert prompt_path.exists()
            prompt_content = prompt_path.read_text()
            
            # Verify Context injection
            # input.input_file should be absolute path
            abs_path = str((uploads_dir / "input_file").absolute())
            assert f"input_file: {abs_path}" in prompt_content
            
            # parameter.divisor should be 5
            assert "divisor: 5" in prompt_content
    finally:
        config.defrost()
        config.GEMINI.DEFAULT_PROMPT_TEMPLATE = old_template
        config.freeze()

@pytest.mark.asyncio
async def test_run_missing_file_strict(adapter, mock_skill, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "input.json").write_text("{}")
    
    # Mock uploads - but DO NOT create "input_file"
    uploads_dir = run_dir / "uploads"
    uploads_dir.mkdir()
    
    input_data = {
        "parameter": {"divisor": 5}
    }
    options = {}

    # Create dummy template
    template_file = tmp_path / "template.j2"
    template_file.write_text(
        "{% for key, val in input.items() %}\n"
        "{{ key }}: {{ val }}\n"
        "{% endfor %}"
    )
    
    from server.config import config
    old_template = config.GEMINI.DEFAULT_PROMPT_TEMPLATE
    config.defrost()
    config.GEMINI.DEFAULT_PROMPT_TEMPLATE = str(template_file)
    config.freeze()
    
    try:
         with patch("server.services.config_generator.config_generator.generate_config"), \
              patch("server.services.skill_patcher.skill_patcher.patch_skill_md"), \
              patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
             
            mock_proc = MagicMock()
            mock_proc.stdout = MagicMock()
            mock_proc.stderr = MagicMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[b""])
            mock_proc.stderr.read = AsyncMock(side_effect=[b""])
            mock_proc.wait = AsyncMock()
            mock_exec.return_value = mock_proc
            with pytest.raises(ValueError, match="Missing required input files"):
                await adapter.run(mock_skill, input_data, run_dir, options)
    finally:
        config.defrost()
        config.GEMINI.DEFAULT_PROMPT_TEMPLATE = old_template
        config.freeze()


def test_extract_session_handle_missing_session_id_raises(adapter):
    with pytest.raises(RuntimeError, match="SESSION_RESUME_FAILED"):
        adapter.extract_session_handle('{"response":{"text":"ok"}}', turn_index=1)


def test_extract_session_handle_from_json_body(adapter):
    handle = adapter.extract_session_handle(
        '{"session_id":"sess_42","response":{"text":"ok"}}',
        turn_index=2,
    )
    assert handle.handle_value == "sess_42"
    assert handle.created_at_turn == 2


def test_parse_output_valid_ask_user_envelope(adapter):
    raw = json.dumps(
        {
            "response": json.dumps(
                {
                    "outcome": "ask_user",
                    "interaction": {
                        "interaction_id": 9,
                        "kind": "open_text",
                        "prompt": "provide more detail",
                    },
                }
            )
        }
    )
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.ASK_USER
    assert result.interaction is not None
    assert result.interaction.interaction_id == 9


def test_parse_output_invalid_ask_user_payload_returns_error(adapter):
    raw = json.dumps(
        {
            "response": json.dumps(
                {
                    "outcome": "ask_user",
                    "interaction": {
                        "kind": "open_text",
                        "prompt": "missing interaction id",
                    },
                }
            )
        }
    )
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.ERROR


@pytest.mark.asyncio
async def test_execute_resume_command_contains_resume_flag(adapter, mock_skill, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "logs").mkdir()

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
            mock_skill,
            options={
                "__resume_session_handle": {
                    "engine": "gemini",
                    "handle_type": "session_id",
                    "handle_value": "sess_1",
                    "created_at_turn": 1,
                }
            },
        )
        args, _ = mock_exec.call_args
        assert "--resume" in args
        assert "sess_1" in args
        assert "--yolo" not in args


@pytest.mark.asyncio
async def test_execute_interactive_command_excludes_yolo(adapter, mock_skill, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "logs").mkdir()

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
            mock_skill,
            options={"execution_mode": "interactive"},
        )
        args, _ = mock_exec.call_args
        assert "--yolo" not in args


@pytest.mark.asyncio
async def test_execute_auto_command_includes_yolo(adapter, mock_skill, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "logs").mkdir()

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
            mock_skill,
            options={"execution_mode": "auto"},
        )
        args, _ = mock_exec.call_args
        assert "--yolo" in args
