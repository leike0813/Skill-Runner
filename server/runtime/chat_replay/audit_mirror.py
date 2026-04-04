from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from server.runtime.common.async_audit_writer import BufferedAsyncTextFileWriter, audit_writer_registry


def _append_jsonl_sync(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False))
        fp.write("\n")


class ChatReplayAuditMirrorWriter:
    def __init__(self) -> None:
        self._writers_by_path: dict[str, BufferedAsyncTextFileWriter] = {}
        self._writers_by_run: dict[str, set[BufferedAsyncTextFileWriter]] = {}

    def _writer_for(self, *, run_dir: Path, run_id: str) -> BufferedAsyncTextFileWriter:
        path = run_dir / ".audit" / "chat_replay.jsonl"
        key = str(path.resolve(strict=False))
        writer = self._writers_by_path.get(key)
        if writer is None:
            writer = BufferedAsyncTextFileWriter(path=path)
            self._writers_by_path[key] = writer
            self._writers_by_run.setdefault(run_id, set()).add(writer)
            audit_writer_registry.register(run_id=run_id, writer=writer)
        return writer

    def enqueue(self, *, run_dir: Path, row: dict[str, Any]) -> None:
        run_id_obj = row.get("run_id")
        run_id = run_id_obj if isinstance(run_id_obj, str) and run_id_obj else run_dir.name
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            _append_jsonl_sync(run_dir / ".audit" / "chat_replay.jsonl", row)
            return
        writer = self._writer_for(run_dir=run_dir, run_id=run_id)
        writer.enqueue(f"{json.dumps(row, ensure_ascii=False)}\n")

    async def drain(self, *, run_id: str | None = None) -> None:
        if run_id is None:
            writers = list(self._writers_by_path.values())
        else:
            writers = list(self._writers_by_run.get(run_id, set()))
        if not writers:
            return
        await asyncio.gather(*(writer.wait_for_idle() for writer in writers), return_exceptions=True)
