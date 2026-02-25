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
    output_schema = {
        "type": "object",
        "required": ["value"],
        "properties": {"value": {"type": "integer"}},
    }
    (skill_dir / "output.schema.json").write_text(json.dumps(output_schema))
    
    return SkillManifest(
        id="test-skill",
        path=skill_dir,
        schemas={
            "input": "input.schema.json",
            "parameter": "parameter.schema.json",
            "output": "output.schema.json",
        }
    )


def test_construct_config_includes_engine_default_layer(tmp_path):
    adapter = GeminiAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill_dir = tmp_path / "skill"
    skill_assets = skill_dir / "assets"
    skill_assets.mkdir(parents=True)
    (skill_assets / "gemini_settings.json").write_text(
        json.dumps({"model": {"name": "gemini-skill-default"}}),
        encoding="utf-8",
    )
    skill = SkillManifest(id="test-skill", path=skill_dir)

    captured: dict[str, object] = {}

    def _capture_generate_config(schema_name: str, config_layers, output_path: Path):
        captured["schema_name"] = schema_name
        captured["layers"] = config_layers
        captured["output_path"] = output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("{}", encoding="utf-8")
        return output_path

    with patch("server.adapters.gemini_adapter.config_generator.generate_config", side_effect=_capture_generate_config):
        adapter._construct_config(
            skill,
            run_dir,
            options={"model": "gemini-runtime", "gemini_config": {"sandbox": {"enabled": False}}},
        )

    assert captured["schema_name"] == "gemini_settings_schema.json"
    layers = captured["layers"]
    assert isinstance(layers, list)
    assert layers[0]["model"]["name"] == "gemini-2.5-flash"
    assert layers[1]["model"]["name"] == "gemini-skill-default"
    assert layers[2]["model"]["name"] == "gemini-runtime"
    assert layers[3]["sandbox"]["enabled"] is False

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
              patch("server.services.skill_patcher.skill_patcher.patch_skill_md") as mock_patch, \
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
            
            # Check rendered prompt passed to Gemini CLI
            args, _ = mock_exec.call_args
            prompt_content = args[-1]
            
            # Verify Context injection
            # input.input_file should be absolute path
            abs_path = str((uploads_dir / "input_file").absolute())
            assert f"input_file: {abs_path}" in prompt_content
            
            # parameter.divisor should be 5
            assert "divisor: 5" in prompt_content
            assert mock_patch.call_count == 1
            _, kwargs = mock_patch.call_args
            assert "output_schema" in kwargs
            assert isinstance(kwargs["output_schema"], dict)
            assert kwargs["output_schema"]["type"] == "object"
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
              patch("server.services.skill_patcher.skill_patcher.patch_skill_md") as mock_patch, \
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
            assert mock_patch.call_count == 1
            _, kwargs = mock_patch.call_args
            assert "output_schema" in kwargs
            assert isinstance(kwargs["output_schema"], dict)
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


def test_extract_session_handle_from_plain_text_fallback(adapter):
    handle = adapter.extract_session_handle(
        'noise {"session_id":"sess_from_text"}',
        turn_index=1,
    )
    assert handle.handle_value == "sess_from_text"


def test_parse_runtime_stream_falls_back_to_stdout_json_lines(adapter):
    parsed = adapter.parse_runtime_stream(
        stdout_raw=b'{"session_id":"sess_stdout","response":"hello from stdout"}\n',
        stderr_raw=b"",
        pty_raw=b"",
    )
    assert parsed["session_id"] == "sess_stdout"
    assert parsed["assistant_messages"]
    assert parsed["assistant_messages"][0]["text"] == "hello from stdout"
    assert "GEMINI_STREAM_JSON_FALLBACK_USED" in parsed["diagnostics"]


def test_parse_runtime_stream_parses_pretty_json_from_stdout(adapter):
    stdout = (
        "YOLO mode is enabled. All tool calls will be automatically approved.\n"
        "{\n"
        '  "session_id": "sess_pretty",\n'
        '  "response": "hello from pretty stdout",\n'
        '  "stats": {"ok": true}\n'
        "}\n"
    ).encode("utf-8")
    parsed = adapter.parse_runtime_stream(
        stdout_raw=stdout,
        stderr_raw=b"",
        pty_raw=b"",
    )
    assert parsed["session_id"] == "sess_pretty"
    assert parsed["assistant_messages"]
    assert parsed["assistant_messages"][0]["text"] == "hello from pretty stdout"
    assert "GEMINI_STREAM_JSON_FALLBACK_USED" in parsed["diagnostics"]


def test_parse_runtime_stream_prefers_split_stream_over_pty_duplicate(adapter):
    split_json = (
        "{\n"
        '  "session_id": "sess_split",\n'
        '  "response": "hello from split",\n'
        '  "stats": {"ok": true}\n'
        "}\n"
    ).encode("utf-8")
    pty_json = (
        "Script started on ...\n"
        "{\n"
        '  "session_id": "sess_split",\n'
        '  "response": "hello from split",\n'
        '  "stats": {"ok": true}\n'
        "}\n"
        "Script done on ...\n"
    ).encode("utf-8")
    parsed = adapter.parse_runtime_stream(
        stdout_raw=split_json,
        stderr_raw=b"",
        pty_raw=pty_json,
    )
    assert parsed["session_id"] == "sess_split"
    assert len(parsed["assistant_messages"]) == 1
    assert parsed["assistant_messages"][0]["text"] == "hello from split"
    assert "PTY_FALLBACK_USED" not in parsed["diagnostics"]
    assert all(row["stream"] != "pty" for row in parsed["raw_rows"])


def test_parse_runtime_stream_falls_back_to_pty_json_lines(adapter):
    parsed = adapter.parse_runtime_stream(
        stdout_raw=b"",
        stderr_raw=b"",
        pty_raw=b'{"session_id":"sess_pty","response":"hello from pty"}\n',
    )
    assert parsed["session_id"] == "sess_pty"
    assert parsed["assistant_messages"]
    assert parsed["assistant_messages"][0]["text"] == "hello from pty"
    assert "GEMINI_STREAM_JSON_FALLBACK_USED" in parsed["diagnostics"]


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
        assert "--yolo" in args


@pytest.mark.asyncio
async def test_execute_interactive_command_includes_yolo(adapter, mock_skill, tmp_path):
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
        assert "--yolo" in args


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
