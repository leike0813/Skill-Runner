from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


def _append_jsonl_sync(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(row, ensure_ascii=False))
        fp.write("\n")


class ChatReplayAuditMirrorWriter:
    async def append_row(self, *, run_dir: Path, row: dict[str, Any]) -> None:
        path = run_dir / ".audit" / "chat_replay.jsonl"
        await asyncio.to_thread(_append_jsonl_sync, path, row)

    def enqueue(self, *, run_dir: Path, row: dict[str, Any]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            _append_jsonl_sync(run_dir / ".audit" / "chat_replay.jsonl", row)
            return
        loop.create_task(self.append_row(run_dir=run_dir, row=row))
