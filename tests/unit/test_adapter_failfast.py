import asyncio
import os
import time
from pathlib import Path

import pytest

from server.adapters.base import EngineAdapter, ProcessExecutionResult
from server.models import AdapterTurnOutcome, AdapterTurnResult, SkillManifest


class _TestAdapter(EngineAdapter):
    def _construct_config(self, skill: SkillManifest, run_dir: Path, options):
        return run_dir / "dummy.json"

    def _setup_environment(self, skill: SkillManifest, run_dir: Path, config_path: Path, options):
        return run_dir

    def _build_prompt(self, skill: SkillManifest, run_dir: Path, input_data):
        return "noop"

    async def _execute_process(self, prompt: str, run_dir: Path, skill: SkillManifest, options) -> ProcessExecutionResult:
        proc = await self._create_subprocess(
            *options["command"],
            cwd=run_dir,
            env=os.environ.copy(),
        )
        return await self._capture_process_output(proc, run_dir, options, "Test")

    def _parse_output(self, raw_stdout: str):
        return AdapterTurnResult(outcome=AdapterTurnOutcome.FINAL, final_data={})


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


@pytest.mark.asyncio
async def test_timeout_terminates_process_group_and_returns_promptly(tmp_path: Path):
    adapter = _TestAdapter()
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    result = await adapter._execute_process(
        "noop",
        run_dir,
        SkillManifest(id="x"),
        {
            "command": [
                "python",
                "-c",
                "import subprocess,sys,time;"
                "subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)']);"
                "print('parent-start', flush=True);"
                "time.sleep(120)",
            ],
            "hard_timeout_seconds": 1,
        },
    )
    elapsed = time.monotonic() - start
    assert result.failure_reason == "TIMEOUT"
    assert elapsed < 20
