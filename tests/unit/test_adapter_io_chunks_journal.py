from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

import pytest

from server.engines.qwen.adapter.execution_adapter import QwenExecutionAdapter
from server.runtime.adapter.base_execution_adapter import EngineExecutionAdapter
from server.runtime.adapter.common.live_stream_parser_common import (
    RUNTIME_STREAM_LINE_OVERFLOW_DIAGNOSTIC_SUBSTITUTED,
    RUNTIME_STREAM_LINE_OVERFLOW_SANITIZED,
)


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


@pytest.mark.asyncio
async def test_capture_process_output_sanitizes_oversized_ndjson_before_io_chunks(tmp_path: Path) -> None:
    class _Emitter:
        def __init__(self) -> None:
            self.text_by_stream: dict[str, list[str]] = {"stdout": [], "stderr": []}
            self.diagnostic_codes: list[str] = []

        async def on_process_started(self, *, event_ts=None) -> None:
            _ = event_ts

        async def on_stream_chunk(
            self,
            *,
            stream: str,
            text: str,
            byte_from: int,
            byte_to: int,
            event_ts=None,
        ) -> None:
            _ = byte_from, byte_to, event_ts
            self.text_by_stream.setdefault(stream, []).append(text)

        async def on_process_exit(self, *, exit_code: int, failure_reason: str | None, event_ts=None) -> None:
            _ = exit_code, failure_reason, event_ts

        async def publish_runtime_diagnostics(self, *, emissions: list[dict], event_ts=None) -> None:
            _ = event_ts
            self.diagnostic_codes.extend(str(item.get("code") or "") for item in emissions)

    run_dir = tmp_path / "run-io-chunks-sanitized"
    run_dir.mkdir(parents=True, exist_ok=True)
    adapter = EngineExecutionAdapter()
    emitter = _Emitter()
    proc = await asyncio.create_subprocess_exec(
        "python",
        "-c",
        (
            "import json,sys;"
            "rows=["
            "{'type':'system','subtype':'init','session_id':'session-1'},"
            "{'type':'user','message':{'role':'user','content':[{'type':'tool_result','tool_use_id':'toolu_1','content':'A'*6000}]}},"
            "{'type':'assistant','message':{'role':'assistant','content':[{'type':'text','text':'after'}]}}"
            "];"
            "sys.stdout.write('\\n'.join(json.dumps(row, ensure_ascii=False) for row in rows)+'\\n')"
        ),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    result = await adapter._capture_process_output(  # noqa: SLF001
        proc=proc,
        run_dir=run_dir,
        options={"__attempt_number": 1, "__engine_name": "claude"},
        prefix="Test",
        live_runtime_emitter=emitter,
    )

    audit_dir = run_dir / ".audit"
    io_chunks_path = audit_dir / "io_chunks.1.jsonl"
    stdout_path = audit_dir / "stdout.1.log"
    rows = [
        json.loads(line)
        for line in io_chunks_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    reconstructed = bytearray()
    for row in rows:
        payload = base64.b64decode(row["payload_b64"], validate=True)
        reconstructed.extend(payload)
        assert len(payload) <= 4096

    stdout_text = stdout_path.read_text(encoding="utf-8")
    assert reconstructed.decode("utf-8") == stdout_text == result.raw_stdout == "".join(emitter.text_by_stream["stdout"])
    assert RUNTIME_STREAM_LINE_OVERFLOW_SANITIZED in emitter.diagnostic_codes

    lines = stdout_text.splitlines()
    assert len(lines) == 3
    assert json.loads(lines[0])["type"] == "system"
    overflow_row = json.loads(lines[1])
    assert overflow_row["type"] == "user"
    overflow_text = overflow_row["message"]["content"][0]["content"]
    assert "[truncated by live overflow guard]" in overflow_text
    assert len(overflow_text) < 6000
    assert json.loads(lines[2])["message"]["content"][0]["text"] == "after"
    overflow_index_path = audit_dir / "overflow_index.1.jsonl"
    assert overflow_index_path.exists()
    overflow_index_rows = [
        json.loads(line)
        for line in overflow_index_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(overflow_index_rows) == 1
    overflow_index = overflow_index_rows[0]
    assert overflow_index["disposition"] == "sanitized"
    raw_sidecar_path = run_dir / overflow_index["raw_relpath"]
    assert raw_sidecar_path.exists()
    raw_sidecar_text = raw_sidecar_path.read_text(encoding="utf-8")
    assert raw_sidecar_text.count("A") >= 6000
    assert '"tool_use_id": "toolu_1"' in raw_sidecar_text
    assert len(raw_sidecar_text) > len(lines[1])
    assert overflow_index["head_preview"]
    assert overflow_index["tail_preview"]


@pytest.mark.asyncio
async def test_capture_process_output_preserves_oversized_qwen_assistant_message_in_io_chunks(tmp_path: Path) -> None:
    class _Emitter:
        def __init__(self) -> None:
            self.text_by_stream: dict[str, list[str]] = {"stdout": [], "stderr": []}
            self.diagnostic_codes: list[str] = []

        async def on_process_started(self, *, event_ts=None) -> None:
            _ = event_ts

        async def on_stream_chunk(
            self,
            *,
            stream: str,
            text: str,
            byte_from: int,
            byte_to: int,
            event_ts=None,
        ) -> None:
            _ = byte_from, byte_to, event_ts
            self.text_by_stream.setdefault(stream, []).append(text)

        async def on_process_exit(self, *, exit_code: int, failure_reason: str | None, event_ts=None) -> None:
            _ = exit_code, failure_reason, event_ts

        async def publish_runtime_diagnostics(self, *, emissions: list[dict], event_ts=None) -> None:
            _ = event_ts
            self.diagnostic_codes.extend(str(item.get("code") or "") for item in emissions)

    run_dir = tmp_path / "run-io-chunks-qwen-exempt"
    run_dir.mkdir(parents=True, exist_ok=True)
    adapter = QwenExecutionAdapter()
    emitter = _Emitter()
    assistant_text = "assistant-" + ("Q" * 6000)
    proc = await asyncio.create_subprocess_exec(
        "python",
        "-c",
        (
            "import json,sys;"
            "rows=["
            "{'type':'system','subtype':'init','session_id':'session-qwen'},"
            "{'type':'assistant','message':{'content':[{'type':'text','text':"
            + json.dumps(assistant_text)
            + "}]}},"
            "{'type':'result','subtype':'success','session_id':'session-qwen','result':'done'}"
            "];"
            "sys.stdout.write('\\n'.join(json.dumps(row, ensure_ascii=False) for row in rows)+'\\n')"
        ),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    result = await adapter._capture_process_output(  # noqa: SLF001
        proc=proc,
        run_dir=run_dir,
        options={"__attempt_number": 1, "__engine_name": "qwen"},
        prefix="Test",
        live_runtime_emitter=emitter,
    )

    audit_dir = run_dir / ".audit"
    io_chunks_path = audit_dir / "io_chunks.1.jsonl"
    stdout_path = audit_dir / "stdout.1.log"
    rows = [
        json.loads(line)
        for line in io_chunks_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    reconstructed = bytearray()
    max_payload_len = 0
    for row in rows:
        payload = base64.b64decode(row["payload_b64"], validate=True)
        reconstructed.extend(payload)
        max_payload_len = max(max_payload_len, len(payload))

    stdout_text = stdout_path.read_text(encoding="utf-8")
    assert reconstructed.decode("utf-8") == stdout_text == result.raw_stdout == "".join(emitter.text_by_stream["stdout"])
    assert RUNTIME_STREAM_LINE_OVERFLOW_SANITIZED not in emitter.diagnostic_codes
    assert max_payload_len > 4096
    payload_lines = [json.loads(line) for line in stdout_text.splitlines()]
    assert payload_lines[1]["message"]["content"][0]["text"] == assistant_text


@pytest.mark.asyncio
async def test_capture_process_output_quarantines_unrepairable_overflow_into_sidecar(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-io-chunks-overflow-substituted"
    run_dir.mkdir(parents=True, exist_ok=True)
    adapter = EngineExecutionAdapter()

    proc = await asyncio.create_subprocess_exec(
        "python",
        "-c",
        "import sys; sys.stdout.write('X'*5000 + '\\n')",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    result = await adapter._capture_process_output(  # noqa: SLF001
        proc=proc,
        run_dir=run_dir,
        options={"__attempt_number": 1, "__engine_name": "claude"},
        prefix="Test",
        live_runtime_emitter=None,
    )

    assert result.exit_code == 0
    audit_dir = run_dir / ".audit"
    stdout_path = audit_dir / "stdout.1.log"
    stdout_payload = json.loads(stdout_path.read_text(encoding="utf-8").strip())
    assert stdout_payload["code"] == RUNTIME_STREAM_LINE_OVERFLOW_DIAGNOSTIC_SUBSTITUTED
    overflow_index_rows = [
        json.loads(line)
        for line in (audit_dir / "overflow_index.1.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(overflow_index_rows) == 1
    overflow_index = overflow_index_rows[0]
    assert overflow_index["disposition"] == "substituted"
    raw_sidecar_path = run_dir / overflow_index["raw_relpath"]
    assert raw_sidecar_path.exists()
    raw_sidecar_text = raw_sidecar_path.read_text(encoding="utf-8")
    assert raw_sidecar_text == ("X" * 5000) + "\n"
    assert stdout_payload["raw_relpath"] == overflow_index["raw_relpath"]
