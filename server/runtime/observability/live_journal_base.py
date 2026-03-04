from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Tuple


@dataclass
class _RunJournalBuffer:
    events: Deque[dict[str, Any]] = field(default_factory=deque)
    subscribers: list[asyncio.Queue[dict[str, Any]]] = field(default_factory=list)
    terminal_at: float | None = None


class _BaseLiveJournal:
    def __init__(self, *, max_events_per_run: int, terminal_retention_sec: float) -> None:
        self._max_events_per_run = max(64, int(max_events_per_run))
        self._terminal_retention_sec = max(1.0, float(terminal_retention_sec))
        self._buffers: Dict[str, _RunJournalBuffer] = {}
        self._lock = threading.Lock()

    def publish(self, *, run_id: str, row: dict[str, Any], terminal: bool = False) -> dict[str, Any]:
        with self._lock:
            self._cleanup_expired_locked()
            buffer = self._buffers.setdefault(run_id, _RunJournalBuffer())
            buffer.events.append(dict(row))
            while len(buffer.events) > self._max_events_per_run:
                buffer.events.popleft()
            if terminal:
                buffer.terminal_at = time.monotonic()
            subscribers = list(buffer.subscribers)
        for queue in subscribers:
            try:
                queue.put_nowait(dict(row))
            except asyncio.QueueFull:
                continue
        return dict(row)

    def replay(
        self,
        *,
        run_id: str,
        after_seq: int = 0,
        event_filter: Any | None = None,
    ) -> dict[str, Any]:
        safe_after = max(0, int(after_seq))
        with self._lock:
            self._cleanup_expired_locked()
            buffer = self._buffers.get(run_id)
            rows = list(buffer.events) if buffer is not None else []
        if callable(event_filter):
            rows = [row for row in rows if event_filter(row)]
        rows = [dict(row) for row in rows if int(row.get("seq") or 0) > safe_after]
        floor = 0
        ceiling = 0
        if rows:
            floor = int(rows[0].get("seq") or 0)
            ceiling = int(rows[-1].get("seq") or 0)
        else:
            with self._lock:
                buffer = self._buffers.get(run_id)
                if buffer and buffer.events:
                    floor = int(buffer.events[0].get("seq") or 0)
                    ceiling = int(buffer.events[-1].get("seq") or 0)
        return {
            "events": rows,
            "cursor_floor": floor,
            "cursor_ceiling": ceiling,
            "has_live": bool(rows) or ceiling > 0,
        }

    def subscribe(self, *, run_id: str, max_queue_size: int = 256) -> tuple[asyncio.Queue[dict[str, Any]], Any]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=max_queue_size)
        with self._lock:
            self._cleanup_expired_locked()
            buffer = self._buffers.setdefault(run_id, _RunJournalBuffer())
            buffer.subscribers.append(queue)

        def _unsubscribe() -> None:
            with self._lock:
                buffer = self._buffers.get(run_id)
                if buffer is None:
                    return
                with contextlib.suppress(ValueError):
                    buffer.subscribers.remove(queue)

        import contextlib

        return queue, _unsubscribe

    def has_run(self, run_id: str) -> bool:
        with self._lock:
            self._cleanup_expired_locked()
            buffer = self._buffers.get(run_id)
            return bool(buffer and buffer.events)

    def clear(self, run_id: str | None = None) -> None:
        with self._lock:
            if run_id is None:
                self._buffers.clear()
            else:
                self._buffers.pop(run_id, None)

    def _cleanup_expired_locked(self) -> None:
        if not self._buffers:
            return
        now = time.monotonic()
        expired = [
            run_id
            for run_id, buffer in self._buffers.items()
            if buffer.terminal_at is not None and (now - buffer.terminal_at) > self._terminal_retention_sec
        ]
        for run_id in expired:
            self._buffers.pop(run_id, None)
