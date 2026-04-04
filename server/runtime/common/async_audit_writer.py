from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque

logger = logging.getLogger(__name__)


def _append_text_sync(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(text)


class BufferedAsyncTextFileWriter:
    def __init__(
        self,
        *,
        path: Path,
        max_buffered_bytes: int = 4 * 1024 * 1024,
        batch_bytes: int = 256 * 1024,
    ) -> None:
        self._path = path
        self._max_buffered_bytes = max(1, int(max_buffered_bytes))
        self._batch_bytes = max(1, int(batch_bytes))
        self._pending_chunks: Deque[str] = deque()
        self._pending_bytes = 0
        self._wake_event = asyncio.Event()
        self._idle_event = asyncio.Event()
        self._idle_event.set()
        self._closed = False
        self._overflow_warned = False
        self._task = asyncio.create_task(self._run())
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.touch(exist_ok=True)

    @property
    def has_pending(self) -> bool:
        return not self._idle_event.is_set()

    def enqueue(self, text: str) -> bool:
        if self._closed or not text:
            return False
        text_bytes = len(text.encode("utf-8", errors="replace"))
        if (self._pending_bytes + text_bytes) > self._max_buffered_bytes:
            if not self._overflow_warned:
                logger.warning(
                    "Buffered audit writer overflow path=%s pending_bytes=%s limit_bytes=%s; dropping write",
                    self._path,
                    self._pending_bytes + text_bytes,
                    self._max_buffered_bytes,
                )
                self._overflow_warned = True
            return False
        self._pending_chunks.append(text)
        self._pending_bytes += text_bytes
        self._idle_event.clear()
        self._wake_event.set()
        return True

    async def wait_for_idle(self, *, timeout_sec: float | None = None) -> bool:
        waiter = asyncio.shield(self._idle_event.wait())
        if timeout_sec is None:
            await waiter
            return True
        try:
            await asyncio.wait_for(waiter, timeout=timeout_sec)
            return True
        except asyncio.TimeoutError:
            return False

    def close(self) -> None:
        self._closed = True
        self._wake_event.set()

    async def close_and_wait(self, *, timeout_sec: float | None = None) -> bool:
        self.close()
        task = asyncio.shield(self._task)
        if timeout_sec is None:
            await task
            return True
        try:
            await asyncio.wait_for(task, timeout=timeout_sec)
            return True
        except asyncio.TimeoutError:
            return False

    async def _run(self) -> None:
        while True:
            await self._wake_event.wait()
            self._wake_event.clear()
            while self._pending_chunks:
                batch_parts: list[str] = []
                batch_bytes = 0
                while self._pending_chunks:
                    part = self._pending_chunks[0]
                    part_bytes = len(part.encode("utf-8", errors="replace"))
                    if batch_parts and (batch_bytes + part_bytes) > self._batch_bytes:
                        break
                    self._pending_chunks.popleft()
                    self._pending_bytes -= part_bytes
                    batch_parts.append(part)
                    batch_bytes += part_bytes
                    if batch_bytes >= self._batch_bytes:
                        break
                if not batch_parts:
                    break
                try:
                    await asyncio.to_thread(_append_text_sync, self._path, "".join(batch_parts))
                except OSError:
                    logger.exception("Buffered audit writer append failed path=%s", self._path)
            if not self._pending_chunks:
                self._idle_event.set()
            if self._closed and not self._pending_chunks:
                break


class AuditWriterRegistry:
    def __init__(self) -> None:
        self._writers_by_run: dict[str, set[BufferedAsyncTextFileWriter]] = defaultdict(set)

    def register(self, *, run_id: str | None, writer: BufferedAsyncTextFileWriter) -> None:
        if not isinstance(run_id, str) or not run_id.strip():
            return
        self._writers_by_run[run_id].add(writer)

    def unregister(self, *, run_id: str | None, writer: BufferedAsyncTextFileWriter) -> None:
        if not isinstance(run_id, str) or not run_id.strip():
            return
        writers = self._writers_by_run.get(run_id)
        if not writers:
            return
        writers.discard(writer)
        if not writers:
            self._writers_by_run.pop(run_id, None)

    def has_pending(self, *, run_id: str | None) -> bool:
        if not isinstance(run_id, str) or not run_id.strip():
            return False
        writers = self._writers_by_run.get(run_id, set())
        return any(writer.has_pending for writer in writers)

    async def wait_for_idle(self, *, run_id: str | None, timeout_sec: float | None = None) -> bool:
        if not isinstance(run_id, str) or not run_id.strip():
            return True
        writers = list(self._writers_by_run.get(run_id, set()))
        if not writers:
            return True
        waiter = asyncio.shield(
            asyncio.gather(*(writer.wait_for_idle() for writer in writers), return_exceptions=False)
        )
        if timeout_sec is None:
            await waiter
            return True
        try:
            await asyncio.wait_for(waiter, timeout=timeout_sec)
            return True
        except asyncio.TimeoutError:
            return False


audit_writer_registry = AuditWriterRegistry()
