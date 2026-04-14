from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from server.runtime.common.async_audit_writer import BufferedAsyncTextFileWriter, audit_writer_registry

logger = logging.getLogger(__name__)

_OVERFLOW_RAW_WRITER_MAX_BUFFERED_BYTES = 64 * 1024 * 1024
_OVERFLOW_RAW_WRITER_BATCH_BYTES = 256 * 1024


@dataclass
class OverflowCaptureHandle:
    overflow_id: str
    stream: str
    line_start_byte: int
    raw_relpath: str
    writer: BufferedAsyncTextFileWriter
    sha256_hasher: Any = field(default_factory=hashlib.sha256)
    total_bytes: int = 0


class OverflowSidecarRecorder:
    def __init__(
        self,
        *,
        run_dir: Path,
        attempt_number: int,
        run_id: str | None = None,
    ) -> None:
        self._run_dir = run_dir
        self._attempt_number = max(1, int(attempt_number))
        self._run_id = run_id or run_dir.name
        self._index_path = run_dir / ".audit" / f"overflow_index.{self._attempt_number}.jsonl"
        self._index_writer: BufferedAsyncTextFileWriter | None = None
        self._raw_writers: list[BufferedAsyncTextFileWriter] = []

    def _ensure_index_writer(self) -> BufferedAsyncTextFileWriter:
        writer = self._index_writer
        if writer is None:
            writer = BufferedAsyncTextFileWriter(path=self._index_path)
            self._index_writer = writer
            audit_writer_registry.register(run_id=self._run_id, writer=writer)
        return writer

    def start_capture(
        self,
        *,
        stream: str,
        line_start_byte: int,
        initial_text: str,
    ) -> OverflowCaptureHandle:
        overflow_id = uuid.uuid4().hex
        raw_relpath = f".audit/overflow_lines/{self._attempt_number}/{overflow_id}.ndjson"
        raw_path = self._run_dir / raw_relpath
        writer = BufferedAsyncTextFileWriter(
            path=raw_path,
            max_buffered_bytes=_OVERFLOW_RAW_WRITER_MAX_BUFFERED_BYTES,
            batch_bytes=_OVERFLOW_RAW_WRITER_BATCH_BYTES,
        )
        audit_writer_registry.register(run_id=self._run_id, writer=writer)
        self._raw_writers.append(writer)
        handle = OverflowCaptureHandle(
            overflow_id=overflow_id,
            stream=stream,
            line_start_byte=max(0, int(line_start_byte)),
            raw_relpath=raw_relpath,
            writer=writer,
        )
        if initial_text:
            self.append_text(handle=handle, text=initial_text)
        return handle

    def append_text(self, *, handle: OverflowCaptureHandle, text: str) -> None:
        if not text:
            return
        payload = text.encode("utf-8", errors="replace")
        handle.total_bytes += len(payload)
        handle.sha256_hasher.update(payload)
        if not handle.writer.enqueue(text):
            logger.warning(
                "overflow raw writer queue overflowed attempt=%s overflow_id=%s raw_relpath=%s",
                self._attempt_number,
                handle.overflow_id,
                handle.raw_relpath,
            )

    def finalize_capture(
        self,
        *,
        handle: OverflowCaptureHandle,
        disposition: str,
        diagnostic_code: str,
        head_preview: str,
        tail_preview: str,
    ) -> dict[str, Any]:
        row = {
            "overflow_id": handle.overflow_id,
            "attempt_number": self._attempt_number,
            "stream": handle.stream,
            "line_start_byte": handle.line_start_byte,
            "total_bytes": handle.total_bytes,
            "sha256": handle.sha256_hasher.hexdigest(),
            "disposition": disposition,
            "diagnostic_code": diagnostic_code,
            "raw_relpath": handle.raw_relpath,
            "head_preview": head_preview,
            "tail_preview": tail_preview,
        }
        handle.writer.close()
        if not self._ensure_index_writer().enqueue(f"{json.dumps(row, ensure_ascii=False)}\n"):
            logger.warning(
                "overflow index writer queue overflowed attempt=%s overflow_id=%s",
                self._attempt_number,
                handle.overflow_id,
            )
        return row

    async def close_and_wait(self, *, timeout_sec: float | None = None) -> bool:
        if self._index_writer is not None:
            self._index_writer.close()
        for writer in self._raw_writers:
            writer.close()
        tasks = []
        if self._index_writer is not None:
            tasks.append(self._index_writer.close_and_wait(timeout_sec=None))
        tasks.extend(writer.close_and_wait(timeout_sec=None) for writer in self._raw_writers)
        if not tasks:
            return True
        try:
            gather_task = asyncio.shield(asyncio.gather(*tasks, return_exceptions=True))
            if timeout_sec is None:
                await gather_task
            else:
                await asyncio.wait_for(gather_task, timeout=timeout_sec)
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            if self._index_writer is not None:
                audit_writer_registry.unregister(run_id=self._run_id, writer=self._index_writer)
            for writer in self._raw_writers:
                audit_writer_registry.unregister(run_id=self._run_id, writer=writer)
