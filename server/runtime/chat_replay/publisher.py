from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from server.models import ChatReplayEventEnvelope
from server.runtime.protocol.schema_registry import validate_chat_replay_event

from .audit_mirror import ChatReplayAuditMirrorWriter
from .factories import derive_chat_replay_rows_from_fcmp
from .live_journal import chat_replay_live_journal


def _read_jsonl(path: Path) -> List[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: List[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fp:
            for line in fp:
                text = line.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)
    except OSError:
        return []
    return rows


class ChatReplayPublisher:
    def __init__(self, *, mirror_writer: ChatReplayAuditMirrorWriter | None = None) -> None:
        self._mirror_writer = mirror_writer or ChatReplayAuditMirrorWriter()
        self._next_seq_by_run: Dict[str, int] = {}

    def _bootstrap_run(self, *, run_dir: Path, run_id: str) -> None:
        if run_id in self._next_seq_by_run:
            return
        max_seq = 0
        for row in _read_jsonl(run_dir / ".audit" / "chat_replay.jsonl"):
            seq_obj = row.get("seq")
            if isinstance(seq_obj, int):
                max_seq = max(max_seq, seq_obj)
        self._next_seq_by_run[run_id] = max_seq + 1

    def publish(self, *, run_dir: Path, event: ChatReplayEventEnvelope | dict[str, Any]) -> dict[str, Any]:
        row = event.model_dump(mode="json") if isinstance(event, ChatReplayEventEnvelope) else dict(event)
        row.setdefault("protocol_version", "chat-replay/1.0")
        run_id = str(row.get("run_id") or "")
        if not run_id:
            raise ValueError("chat replay publish requires run_id")
        self._bootstrap_run(run_dir=run_dir, run_id=run_id)
        row["seq"] = self._next_seq_by_run[run_id]
        self._next_seq_by_run[run_id] += 1
        created_at = row.get("created_at")
        if isinstance(created_at, datetime):
            row["created_at"] = created_at.isoformat()
        elif not isinstance(created_at, str) or not created_at:
            row["created_at"] = datetime.utcnow().isoformat()
        validate_chat_replay_event(row)
        published = chat_replay_live_journal.publish(
            run_id=run_id,
            row=row,
            terminal=str(row.get("kind") or "") == "orchestration_notice"
            and str((row.get("correlation") or {}).get("status") or "") in {"succeeded", "failed", "canceled"},
        )
        self._mirror_writer.enqueue(run_dir=run_dir, row=published)
        return published

    def publish_from_fcmp(self, *, run_dir: Path, row: dict[str, Any]) -> List[dict[str, Any]]:
        published: List[dict[str, Any]] = []
        for chat_row in derive_chat_replay_rows_from_fcmp(row):
            published.append(self.publish(run_dir=run_dir, event=chat_row))
        return published

    async def drain_mirror(self, *, run_id: str | None = None) -> None:
        drain = getattr(self._mirror_writer, "drain", None)
        if callable(drain):
            await drain(run_id=run_id)


chat_replay_publisher = ChatReplayPublisher()
