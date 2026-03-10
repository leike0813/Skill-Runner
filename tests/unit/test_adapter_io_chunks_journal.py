from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

import pytest

from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter


@pytest.mark.asyncio
async def test_capture_process_output_writes_io_chunks_journal(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-io-chunks"
    run_dir.mkdir(parents=True, exist_ok=True)
    adapter = EngineExecutionAdapter()

    proc = await asyncio.create_subprocess_exec(
        "python",
        "-c",
        "import sys; sys.stdout.buffer.write(b'out-1\\nout-2\\n'); sys.stderr.buffer.write(b'err-1\\n')",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    result = await adapter._capture_process_output(  # noqa: SLF001
        proc=proc,
        run_dir=run_dir,
        options={"__attempt_number": 1},
        prefix="Test",
        live_runtime_emitter=None,
    )

    assert result.exit_code == 0
    audit_dir = run_dir / ".audit"
    io_chunks_path = audit_dir / "io_chunks.1.jsonl"
    stdout_path = audit_dir / "stdout.1.log"
    stderr_path = audit_dir / "stderr.1.log"
    assert io_chunks_path.exists()
    assert stdout_path.exists()
    assert stderr_path.exists()

    rows = [
        json.loads(line)
        for line in io_chunks_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows
    assert [row["seq"] for row in rows] == list(range(1, len(rows) + 1))
    assert all(row["stream"] in {"stdout", "stderr"} for row in rows)

    reconstructed = {"stdout": bytearray(), "stderr": bytearray()}
    for row in rows:
        payload = base64.b64decode(row["payload_b64"], validate=True)
        reconstructed[row["stream"]].extend(payload)

    assert bytes(reconstructed["stdout"]).decode("utf-8") == stdout_path.read_text(encoding="utf-8")
    assert bytes(reconstructed["stderr"]).decode("utf-8") == stderr_path.read_text(encoding="utf-8")
