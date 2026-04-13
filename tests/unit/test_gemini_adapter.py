import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from server.engines.gemini.adapter.execution_adapter import GeminiExecutionAdapter
from server.models import AdapterTurnOutcome, SkillManifest
from server.runtime.adapter.contracts import AdapterExecutionContext


def _stub_generate_config(_schema_name: str, _layers, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("{}", encoding="utf-8")
    return output_path


@pytest.fixture
def adapter():
    adapter = GeminiExecutionAdapter()
    adapter.agent_manager.resolve_engine_command = lambda _engine: Path("/usr/bin/gemini")
    return adapter

@pytest.fixture
def mock_skill(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("skill", encoding="utf-8")
    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    
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
    (assets_dir / "runner.json").write_text(
        json.dumps(
            {
                "id": "test-skill",
                "engines": ["gemini"],
                "execution_modes": ["auto", "interactive"],
                "schemas": {
                    "input": "input.schema.json",
                    "parameter": "parameter.schema.json",
                    "output": "output.schema.json",
                },
            }
        ),
        encoding="utf-8",
    )
    
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
    adapter = GeminiExecutionAdapter()
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

    with patch("server.engines.gemini.adapter.config_composer.config_generator.generate_config", side_effect=_capture_generate_config):
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


def test_construct_config_prefers_runner_declared_skill_config(tmp_path):
    adapter = GeminiExecutionAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill_dir = tmp_path / "skill"
    assets_dir = skill_dir / "assets"
    custom_dir = skill_dir / "custom"
    assets_dir.mkdir(parents=True)
    custom_dir.mkdir()
    (custom_dir / "gemini_settings.json").write_text(
        json.dumps({"model": {"name": "gemini-declared"}}),
        encoding="utf-8",
    )
    (assets_dir / "gemini_settings.json").write_text(
        json.dumps({"model": {"name": "gemini-fallback"}}),
        encoding="utf-8",
    )
    skill = SkillManifest(
        id="test-skill",
        path=skill_dir,
        engine_configs={"gemini": "custom/gemini_settings.json"},
    )

    captured: dict[str, object] = {}

    def _capture_generate_config(schema_name: str, config_layers, output_path: Path):
        captured["layers"] = config_layers
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("{}", encoding="utf-8")
        return output_path

    with patch("server.engines.gemini.adapter.config_composer.config_generator.generate_config", side_effect=_capture_generate_config):
        adapter._construct_config(skill, run_dir, options={})

    layers = captured["layers"]
    assert isinstance(layers, list)
    assert layers[1]["model"]["name"] == "gemini-declared"

@pytest.mark.asyncio
async def test_run_prompt_generation_strict_files(adapter, mock_skill, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    
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

    skill_with_prompt = mock_skill.model_copy(
        update={
            "entrypoint": {"prompts": {"gemini": template_file.read_text(encoding="utf-8")}}
        }
    )

    # Mock dependencies
    with patch(
        "server.engines.common.config.json_layer_config_generator.config_generator.generate_config",
        side_effect=_stub_generate_config,
    ), \
         patch("server.services.skill.skill_patcher.skill_patcher.patch_skill_md") as mock_patch, \
         patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        mock_proc.stdout.read = AsyncMock(side_effect=[b""])
        mock_proc.stderr.read = AsyncMock(side_effect=[b""])
        mock_proc.wait = AsyncMock()
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        await adapter.run(skill_with_prompt, input_data, run_dir, options)

        # Check rendered prompt passed to Gemini CLI
        args, _ = mock_exec.call_args
        prompt_content = args[-1]

        # Verify Context injection
        # input.input_file should be absolute path
        abs_path = str((uploads_dir / "input_file").absolute())
        assert f"input_file: {abs_path}" in prompt_content
        assert "prefer calling that tool instead of directly using `read`" in prompt_content
        assert "./.gemini/skills" in prompt_content

        # parameter.divisor should be 5
        assert "divisor: 5" in prompt_content
        mock_patch.assert_not_called()

@pytest.mark.asyncio
async def test_run_missing_file_strict(adapter, mock_skill, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    
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

    skill_with_prompt = mock_skill.model_copy(
        update={
            "entrypoint": {"prompts": {"gemini": template_file.read_text(encoding="utf-8")}}
        }
    )

    with patch(
        "server.engines.common.config.json_layer_config_generator.config_generator.generate_config",
        side_effect=_stub_generate_config,
    ), \
         patch("server.services.skill.skill_patcher.skill_patcher.patch_skill_md") as mock_patch, \
         patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:

        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        mock_proc.stdout.read = AsyncMock(side_effect=[b""])
        mock_proc.stderr.read = AsyncMock(side_effect=[b""])
        mock_proc.wait = AsyncMock()
        mock_exec.return_value = mock_proc
        with pytest.raises(ValueError, match="Missing required input files"):
            await adapter.run(skill_with_prompt, input_data, run_dir, options)
        mock_patch.assert_not_called()


@pytest.mark.asyncio
async def test_run_persists_first_attempt_prompt_to_request_input(adapter, mock_skill, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    uploads_dir = run_dir / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / "input_file").write_text("content", encoding="utf-8")
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir()
    request_input_path = audit_dir / "request_input.json"
    request_input_path.write_text(json.dumps({"request_id": "req-1"}, ensure_ascii=False), encoding="utf-8")

    input_data = {"parameter": {"divisor": 5}}
    options = {"__attempt_number": 1}
    template_file = tmp_path / "template.j2"
    template_file.write_text("input_file: {{ input.input_file }}\n", encoding="utf-8")
    skill_with_prompt = mock_skill.model_copy(
        update={"entrypoint": {"prompts": {"gemini": template_file.read_text(encoding="utf-8")}}}
    )

    with patch(
        "server.engines.common.config.json_layer_config_generator.config_generator.generate_config",
        side_effect=_stub_generate_config,
    ), patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        mock_proc.stdout.read = AsyncMock(side_effect=[b""])
        mock_proc.stderr.read = AsyncMock(side_effect=[b""])
        mock_proc.wait = AsyncMock()
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        await adapter.run(skill_with_prompt, input_data, run_dir, options)

        args, _ = mock_exec.call_args
        prompt_content = args[-1]
        spawn_command = list(args)
        payload = json.loads(request_input_path.read_text(encoding="utf-8"))
        assert payload["rendered_prompt_first_attempt"] == prompt_content
        assert prompt_content.startswith("If the environment provides a `skill` tool")
        assert "./.gemini/skills" in prompt_content
        assert payload["spawn_command_original_first_attempt"] == spawn_command
        assert payload["spawn_command_effective_first_attempt"] == spawn_command
        assert payload["spawn_command_normalization_applied_first_attempt"] is False
        assert payload["spawn_command_normalization_reason_first_attempt"] == "not_applicable"


@pytest.mark.asyncio
async def test_run_does_not_persist_prompt_after_first_attempt(adapter, mock_skill, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    uploads_dir = run_dir / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / "input_file").write_text("content", encoding="utf-8")
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir()
    request_input_path = audit_dir / "request_input.json"
    request_input_path.write_text(json.dumps({"request_id": "req-1"}, ensure_ascii=False), encoding="utf-8")

    input_data = {"parameter": {"divisor": 5}}
    options = {"__attempt_number": 2}
    template_file = tmp_path / "template.j2"
    template_file.write_text("input_file: {{ input.input_file }}\n", encoding="utf-8")
    skill_with_prompt = mock_skill.model_copy(
        update={"entrypoint": {"prompts": {"gemini": template_file.read_text(encoding="utf-8")}}}
    )

    with patch(
        "server.engines.common.config.json_layer_config_generator.config_generator.generate_config",
        side_effect=_stub_generate_config,
    ), patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        mock_proc.stdout.read = AsyncMock(side_effect=[b""])
        mock_proc.stderr.read = AsyncMock(side_effect=[b""])
        mock_proc.wait = AsyncMock()
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        await adapter.run(skill_with_prompt, input_data, run_dir, options)

    payload = json.loads(request_input_path.read_text(encoding="utf-8"))
    assert "rendered_prompt_first_attempt" not in payload
    assert "spawn_command_original_first_attempt" not in payload
    assert "spawn_command_effective_first_attempt" not in payload
    assert "spawn_command_normalization_applied_first_attempt" not in payload
    assert "spawn_command_normalization_reason_first_attempt" not in payload
    assert not (audit_dir / "prompt.1.txt").exists()
    assert not (audit_dir / "argv.1.json").exists()


@pytest.mark.asyncio
async def test_run_first_attempt_prompt_override_still_gets_global_prefix(adapter, mock_skill, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    uploads_dir = run_dir / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / "input_file").write_text("content", encoding="utf-8")

    input_data = {"parameter": {"divisor": 5}}
    options = {"__attempt_number": 1, "__prompt_override": "OVERRIDE PROMPT"}

    with patch(
        "server.engines.common.config.json_layer_config_generator.config_generator.generate_config",
        side_effect=_stub_generate_config,
    ), patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        mock_proc.stdout.read = AsyncMock(side_effect=[b""])
        mock_proc.stderr.read = AsyncMock(side_effect=[b""])
        mock_proc.wait = AsyncMock()
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        await adapter.run(mock_skill, input_data, run_dir, options)

        args, _ = mock_exec.call_args
        prompt_content = args[-1]
        assert prompt_content.startswith("If the environment provides a `skill` tool")
        assert prompt_content.endswith("OVERRIDE PROMPT")
        assert "\n\nOVERRIDE PROMPT" in prompt_content


@pytest.mark.asyncio
async def test_run_non_first_attempt_prompt_override_does_not_get_global_prefix(adapter, mock_skill, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    uploads_dir = run_dir / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / "input_file").write_text("content", encoding="utf-8")

    input_data = {"parameter": {"divisor": 5}}
    options = {"__attempt_number": 2, "__prompt_override": "OVERRIDE PROMPT"}

    with patch(
        "server.engines.common.config.json_layer_config_generator.config_generator.generate_config",
        side_effect=_stub_generate_config,
    ), patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        mock_proc.stdout.read = AsyncMock(side_effect=[b""])
        mock_proc.stderr.read = AsyncMock(side_effect=[b""])
        mock_proc.wait = AsyncMock()
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        await adapter.run(mock_skill, input_data, run_dir, options)

        args, _ = mock_exec.call_args
        prompt_content = args[-1]
        assert prompt_content == "OVERRIDE PROMPT"


@pytest.mark.asyncio
async def test_run_repair_round_prompt_override_skips_first_attempt_audit_and_prefix(adapter, mock_skill, tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    uploads_dir = run_dir / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / "input_file").write_text("content", encoding="utf-8")
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir()
    request_input_path = audit_dir / "request_input.json"
    request_input_path.write_text(json.dumps({"request_id": "req-1"}, ensure_ascii=False), encoding="utf-8")

    input_data = {"parameter": {"divisor": 5}}
    options = {
        "__attempt_number": 1,
        "__repair_round_index": 1,
        "__prompt_override": "RETURN ONLY JSON",
    }

    with patch(
        "server.engines.common.config.json_layer_config_generator.config_generator.generate_config",
        side_effect=_stub_generate_config,
    ), patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        mock_proc.stdout.read = AsyncMock(side_effect=[b""])
        mock_proc.stderr.read = AsyncMock(side_effect=[b""])
        mock_proc.wait = AsyncMock()
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        await adapter.run(mock_skill, input_data, run_dir, options)

    payload = json.loads(request_input_path.read_text(encoding="utf-8"))
    assert "rendered_prompt_first_attempt" not in payload
    assert "spawn_command_original_first_attempt" not in payload
    assert "spawn_command_effective_first_attempt" not in payload
    assert not (audit_dir / "prompt.1.txt").exists()
    assert not (audit_dir / "argv.1.json").exists()
    args, _ = mock_exec.call_args
    assert args[-1] == "RETURN ONLY JSON"


def test_build_start_and_resume_command_use_first_attempt_effective_prompt(adapter, mock_skill, tmp_path):
    from server.models import EngineSessionHandle, EngineSessionHandleType

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    uploads_dir = run_dir / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / "input_file").write_text("content", encoding="utf-8")
    template_file = tmp_path / "template.j2"
    template_file.write_text("input_file: {{ input.input_file }}\n", encoding="utf-8")
    skill_with_prompt = mock_skill.model_copy(
        update={"entrypoint": {"prompts": {"gemini": template_file.read_text(encoding="utf-8")}}}
    )
    ctx = adapter._build_prompt(  # type: ignore[attr-defined]
        skill_with_prompt,
        run_dir,
        {"parameter": {"divisor": 5}},
        {"__attempt_number": 1},
    )
    assert ctx.startswith("If the environment provides a `skill` tool")
    assert "./.gemini/skills" in ctx

    render_ctx = adapter.build_start_command(
        AdapterExecutionContext(
            skill=skill_with_prompt,
            run_dir=run_dir,
            input_data={"parameter": {"divisor": 5}},
            options={"__attempt_number": 1},
        )
    )
    assert render_ctx[-1].startswith("If the environment provides a `skill` tool")

    resume_command = adapter.build_resume_command(
        AdapterExecutionContext(
            skill=skill_with_prompt,
            run_dir=run_dir,
            input_data={"parameter": {"divisor": 5}},
            options={"__attempt_number": 1},
        ),
        EngineSessionHandle(
            engine="gemini",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="sess-1",
            created_at_turn=1,
        ),
    )
    assert resume_command[-1].startswith("If the environment provides a `skill` tool")


@pytest.mark.asyncio
async def test_run_persists_first_attempt_prompt_to_fallback_when_request_input_invalid(
    adapter,
    mock_skill,
    tmp_path,
):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    uploads_dir = run_dir / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / "input_file").write_text("content", encoding="utf-8")
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir()
    request_input_path = audit_dir / "request_input.json"
    request_input_path.write_text("not-json", encoding="utf-8")

    input_data = {"parameter": {"divisor": 5}}
    options = {"__attempt_number": 1}
    template_file = tmp_path / "template.j2"
    template_file.write_text("input_file: {{ input.input_file }}\n", encoding="utf-8")
    skill_with_prompt = mock_skill.model_copy(
        update={"entrypoint": {"prompts": {"gemini": template_file.read_text(encoding="utf-8")}}}
    )

    with patch(
        "server.engines.common.config.json_layer_config_generator.config_generator.generate_config",
        side_effect=_stub_generate_config,
    ), patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        mock_proc.stderr = MagicMock()
        mock_proc.stdout.read = AsyncMock(side_effect=[b""])
        mock_proc.stderr.read = AsyncMock(side_effect=[b""])
        mock_proc.wait = AsyncMock()
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        await adapter.run(skill_with_prompt, input_data, run_dir, options)
        args, _ = mock_exec.call_args
        prompt_content = args[-1]
        spawn_command = list(args)

    fallback_path = audit_dir / "prompt.1.txt"
    assert fallback_path.exists()
    assert fallback_path.read_text(encoding="utf-8") == prompt_content
    argv_fallback_path = audit_dir / "argv.1.json"
    assert argv_fallback_path.exists()
    argv_payload = json.loads(argv_fallback_path.read_text(encoding="utf-8"))
    assert argv_payload["spawn_command_original_first_attempt"] == spawn_command
    assert argv_payload["spawn_command_effective_first_attempt"] == spawn_command
    assert argv_payload["spawn_command_normalization_applied_first_attempt"] is False
    assert argv_payload["spawn_command_normalization_reason_first_attempt"] == "not_applicable"


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
    run_handle = parsed.get("run_handle")
    assert isinstance(run_handle, dict)
    assert run_handle.get("handle_id") == "sess_stdout"
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
    structured = parsed.get("structured_payloads", [])
    assert isinstance(structured, list) and structured
    parsed_event = structured[0]
    assert parsed_event["type"] == "parsed.json"
    assert parsed_event["stream"] == "stdout"
    assert parsed_event["session_id"] == "sess_pretty"
    assert parsed_event["response"] == "hello from pretty stdout"
    assert isinstance(parsed_event.get("details"), dict)
    run_handle = parsed.get("run_handle")
    assert isinstance(run_handle, dict)
    assert run_handle.get("handle_id") == "sess_pretty"
    turn_complete_data = parsed.get("turn_complete_data")
    assert isinstance(turn_complete_data, dict)
    assert turn_complete_data.get("ok") is True


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


def test_parse_runtime_stream_coalesces_large_raw_stderr_blocks(adapter):
    stderr_lines = "\n".join(f"429 line {idx}" for idx in range(120)) + "\n"
    parsed = adapter.parse_runtime_stream(
        stdout_raw=b"",
        stderr_raw=stderr_lines.encode("utf-8"),
        pty_raw=b"",
    )
    raw_rows = parsed.get("raw_rows", [])
    assert isinstance(raw_rows, list)
    assert len(raw_rows) < 120
    assert "GEMINI_RAW_ROWS_COALESCED" in parsed["diagnostics"]


def test_parse_runtime_stream_uses_latest_response_frame(adapter):
    parsed = adapter.parse_runtime_stream(
        stdout_raw=(
            b'{"session_id":"sess_old","response":"old response"}\n'
            b'{"session_id":"sess_new","response":"latest response"}\n'
        ),
        stderr_raw=b"",
        pty_raw=b"",
    )
    assert parsed["session_id"] == "sess_new"
    assert parsed["assistant_messages"]
    assert [msg["text"] for msg in parsed["assistant_messages"]] == ["latest response"]


def test_live_session_assistant_message_keeps_raw_ref(adapter):
    session = adapter.stream_parser.start_live_session()
    payload = (
        '{"session_id":"gemini-live","response":"hello from live","stats":{"tokens":{"total":1}}}\n'
    )
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
    assert int(raw_ref.get("byte_to", -1)) == len(encoded.rstrip(b"\n"))


def test_parse_runtime_stream_detects_oauth_code_prompt(adapter):
    oauth_prompt = (
        "Please visit the following URL to authorize the application:\n\n"
        "https://accounts.google.com/o/oauth2/v2/auth?... \n\n"
        "Enter the authorization code:"
    ).encode("utf-8")
    parsed = adapter.parse_runtime_stream(
        stdout_raw=oauth_prompt,
        stderr_raw=b"",
        pty_raw=b"",
    )
    assert "GEMINI_OAUTH_CODE_PROMPT_DETECTED" in parsed["diagnostics"]


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
