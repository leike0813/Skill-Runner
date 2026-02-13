from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import pytest
from server.adapters.codex_adapter import CodexAdapter
from server.models import SkillManifest


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
    mock_proc.stdout.readline = AsyncMock(side_effect=[b""])
    mock_proc.stderr.readline = AsyncMock(side_effect=[b""])
    mock_proc.wait = AsyncMock()
    mock_proc.returncode = 0

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = mock_proc
        await adapter._execute_process(prompt, run_dir, skill, options={})

        args, _ = mock_exec.call_args
        assert Path(args[0]).name.startswith("codex")
        assert args[1] == "exec"
        assert "--full-auto" in args
        assert "--json" in args
        assert "-p" in args
        assert "skill-runner" in args
        assert prompt in args
