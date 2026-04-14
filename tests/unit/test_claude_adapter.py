import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.engines.claude.adapter.execution_adapter import ClaudeExecutionAdapter
from server.models import SkillManifest


def _set_output_schema_cli_enabled(adapter: ClaudeExecutionAdapter, enabled: bool) -> None:
    command_features = replace(adapter.profile.command_features, inject_output_schema_cli=enabled)
    adapter.profile = replace(adapter.profile, command_features=command_features)


@pytest.mark.asyncio
async def test_execute_persists_first_attempt_spawn_command_with_json_schema(tmp_path):
    adapter = ClaudeExecutionAdapter()
    _set_output_schema_cli_enabled(adapter, True)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir()
    contracts_dir = audit_dir / "contracts"
    contracts_dir.mkdir()
    request_input_path = audit_dir / "request_input.json"
    request_input_path.write_text(json.dumps({"request_id": "req-1"}), encoding="utf-8")
    (contracts_dir / "target_output_schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
            }
        ),
        encoding="utf-8",
    )
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
        with patch.object(adapter.agent_manager, "resolve_engine_command", return_value=Path("/usr/bin/claude")):
            await adapter._execute_process(
                "schema prompt",
                run_dir,
                skill,
                options={
                    "__attempt_number": 1,
                    "__target_output_schema_relpath": ".audit/contracts/target_output_schema.json",
                },
            )

    args, _ = mock_exec.call_args
    payload = json.loads(request_input_path.read_text(encoding="utf-8"))
    assert payload["spawn_command_original_first_attempt"] == list(args)
    assert payload["spawn_command_effective_first_attempt"] == list(args)
    assert "--output-format" in args
    assert args[args.index("--output-format") + 1] == "stream-json"
    assert "--json-schema" in args
    inline_schema = args[args.index("--json-schema") + 1]
    assert isinstance(json.loads(inline_schema), dict)
    assert json.loads(inline_schema)["properties"]["ok"]["type"] == "boolean"


@pytest.mark.asyncio
async def test_execute_skips_json_schema_when_materialized_schema_is_missing(tmp_path):
    adapter = ClaudeExecutionAdapter()
    _set_output_schema_cli_enabled(adapter, True)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    audit_dir = run_dir / ".audit"
    audit_dir.mkdir()
    request_input_path = audit_dir / "request_input.json"
    request_input_path.write_text(json.dumps({"request_id": "req-1"}), encoding="utf-8")
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
        with patch.object(adapter.agent_manager, "resolve_engine_command", return_value=Path("/usr/bin/claude")):
            await adapter._execute_process(
                "schema prompt",
                run_dir,
                skill,
                options={
                    "__attempt_number": 1,
                    "__target_output_schema_relpath": ".audit/contracts/target_output_schema.json",
                },
            )

    args, _ = mock_exec.call_args
    assert "--json-schema" not in args
