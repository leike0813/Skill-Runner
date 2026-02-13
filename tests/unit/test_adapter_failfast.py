import asyncio
from pathlib import Path

import pytest

from server.adapters.base import EngineAdapter, ProcessExecutionResult
from server.models import SkillManifest


class _TestAdapter(EngineAdapter):
    def _construct_config(self, skill: SkillManifest, run_dir: Path, options):
        return run_dir / "dummy.json"

    def _setup_environment(self, skill: SkillManifest, run_dir: Path, config_path: Path):
        return run_dir

    def _build_prompt(self, skill: SkillManifest, run_dir: Path, input_data):
        return "noop"

    async def _execute_process(self, prompt: str, run_dir: Path, skill: SkillManifest, options) -> ProcessExecutionResult:
        proc = await asyncio.create_subprocess_exec(
            *options["command"],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(run_dir),
        )
        return await self._capture_process_output(proc, run_dir, options, "Test")

    def _parse_output(self, raw_stdout: str):
        return None


@pytest.mark.asyncio
async def test_capture_process_output_timeout_classified(tmp_path: Path):
    adapter = _TestAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    result = await adapter._execute_process(
        "noop",
        run_dir,
        SkillManifest(id="x"),
        {
            "command": ["python", "-c", "import time; time.sleep(2)"],
            "hard_timeout_seconds": 1,
        },
    )
    assert result.failure_reason == "TIMEOUT"
    assert result.exit_code != 0


@pytest.mark.asyncio
async def test_capture_process_output_auth_required_classified(tmp_path: Path):
    adapter = _TestAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    result = await adapter._execute_process(
        "noop",
        run_dir,
        SkillManifest(id="x"),
        {
            "command": ["python", "-c", "import sys; sys.stderr.write('SERVER_OAUTH2_REQUIRED'); sys.exit(1)"],
            "hard_timeout_seconds": 10,
        },
    )
    assert result.failure_reason == "AUTH_REQUIRED"


@pytest.mark.asyncio
async def test_capture_process_output_stream_writes_logs_during_run(tmp_path: Path):
    adapter = _TestAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        "python",
        "-c",
        "import sys,time;sys.stdout.write('tick\\n');sys.stdout.flush();time.sleep(1);sys.stdout.write('done\\n');sys.stdout.flush()",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(run_dir),
    )
    task = asyncio.create_task(adapter._capture_process_output(proc, run_dir, {"hard_timeout_seconds": 10}, "Test"))
    await asyncio.sleep(0.2)
    stdout_log = run_dir / "logs" / "stdout.txt"
    assert stdout_log.exists()
    partial = stdout_log.read_text(encoding="utf-8")
    assert "tick" in partial
    result = await task
    assert "done" in result.raw_stdout
