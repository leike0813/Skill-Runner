import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from server.engines.claude.adapter.execution_adapter import ClaudeExecutionAdapter
from server.models import SkillManifest


@pytest.mark.asyncio
async def test_execute_persists_first_attempt_spawn_command_with_json_schema(tmp_path):
    adapter = ClaudeExecutionAdapter()
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
    payload = json.loads(request_input_path.read_text(encoding="utf-8"))
    assert payload["spawn_command_original_first_attempt"] == list(args)
    assert payload["spawn_command_effective_first_attempt"] == list(args)
    assert "--output-format" in args
    assert args[args.index("--output-format") + 1] == "json"
    assert "--json-schema" in args
    assert args[args.index("--json-schema") + 1] == ".audit/contracts/target_output_schema.json"
