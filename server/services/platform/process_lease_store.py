from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.config import config
from server.services.platform import aiosqlite_compat as aiosqlite
from server.services.platform.sqlite_db_handle import sqlite_sync_bridge

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ProcessLeaseStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or Path(config.SYSTEM.PROCESS_LEASES_DB)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async def _operation(conn: aiosqlite.Connection) -> None:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS process_leases (
                    lease_id TEXT PRIMARY KEY,
                    owner_kind TEXT,
                    owner_id TEXT,
                    pid INTEGER,
                    request_id TEXT,
                    run_id TEXT,
                    attempt_number INTEGER,
                    engine TEXT,
                    transport TEXT,
                    metadata_json TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    closed_at TEXT,
                    close_reason TEXT
                )
                """
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_process_leases_status ON process_leases(status)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_process_leases_updated_at ON process_leases(updated_at)"
            )
            await conn.commit()

        sqlite_sync_bridge.run(_operation, db_path=self._db_path)
        self._initialized = True

    @staticmethod
    def _metadata_to_json(payload: dict[str, Any]) -> str | None:
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            return None
        try:
            import json
            return json.dumps(metadata, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            logger.warning("Process lease metadata serialization failed", exc_info=True)
            return None

    @staticmethod
    def _row_to_payload(row: Any) -> dict[str, Any]:
        import json

        payload: dict[str, Any] = {
            "lease_id": row["lease_id"],
            "owner_kind": row["owner_kind"],
            "owner_id": row["owner_id"],
            "pid": row["pid"],
            "request_id": row["request_id"],
            "run_id": row["run_id"],
            "attempt_number": row["attempt_number"],
            "engine": row["engine"],
            "transport": row["transport"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        if row["closed_at"] is not None:
            payload["closed_at"] = row["closed_at"]
        if row["close_reason"] is not None:
            payload["close_reason"] = row["close_reason"]
        metadata_raw = row["metadata_json"]
        if isinstance(metadata_raw, str) and metadata_raw.strip():
            try:
                metadata = json.loads(metadata_raw)
            except json.JSONDecodeError:
                metadata = None
            if isinstance(metadata, dict):
                payload["metadata"] = metadata
        return payload

    def upsert_active(self, lease_payload: dict[str, Any]) -> None:
        self._ensure_initialized()
        lease_id_raw = lease_payload.get("lease_id")
        if not isinstance(lease_id_raw, str) or not lease_id_raw.strip():
            raise ValueError("lease_payload.lease_id is required")
        payload = dict(lease_payload)
        payload["status"] = "active"
        payload.setdefault("updated_at", _utc_now_iso())
        payload.setdefault("created_at", payload["updated_at"])
        async def _operation(conn: aiosqlite.Connection) -> None:
            await conn.execute(
                """
                INSERT INTO process_leases (
                    lease_id, owner_kind, owner_id, pid, request_id, run_id,
                    attempt_number, engine, transport, metadata_json,
                    status, created_at, updated_at, closed_at, close_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                ON CONFLICT(lease_id) DO UPDATE SET
                    owner_kind=excluded.owner_kind,
                    owner_id=excluded.owner_id,
                    pid=excluded.pid,
                    request_id=excluded.request_id,
                    run_id=excluded.run_id,
                    attempt_number=excluded.attempt_number,
                    engine=excluded.engine,
                    transport=excluded.transport,
                    metadata_json=excluded.metadata_json,
                    status='active',
                    updated_at=excluded.updated_at,
                    closed_at=NULL,
                    close_reason=NULL
                """,
                (
                    lease_id_raw,
                    payload.get("owner_kind"),
                    payload.get("owner_id"),
                    payload.get("pid"),
                    payload.get("request_id"),
                    payload.get("run_id"),
                    payload.get("attempt_number"),
                    payload.get("engine"),
                    payload.get("transport"),
                    self._metadata_to_json(payload),
                    "active",
                    payload["created_at"],
                    payload["updated_at"],
                ),
            )
            await conn.commit()

        sqlite_sync_bridge.run(_operation, db_path=self._db_path)

    def get(self, lease_id: str) -> dict[str, Any] | None:
        self._ensure_initialized()
        safe = lease_id.strip()
        if not safe:
            return None
        async def _operation(conn: aiosqlite.Connection) -> Any:
            cursor = await conn.execute(
                "SELECT * FROM process_leases WHERE lease_id = ?",
                (safe,),
            )
            return await cursor.fetchone()

        row = sqlite_sync_bridge.run(_operation, db_path=self._db_path)
        if row is None:
            return None
        return self._row_to_payload(row)

    def close(self, lease_id: str, *, reason: str, closed_at: str | None = None) -> None:
        self._ensure_initialized()
        safe = lease_id.strip()
        if not safe:
            return
        closed_ts = closed_at or _utc_now_iso()

        async def _operation(conn: aiosqlite.Connection) -> None:
            cursor = await conn.execute(
                "SELECT lease_id FROM process_leases WHERE lease_id = ?",
                (safe,),
            )
            if await cursor.fetchone() is None:
                return
            await conn.execute(
                """
                UPDATE process_leases
                SET status = 'closed',
                    close_reason = ?,
                    closed_at = ?,
                    updated_at = ?
                WHERE lease_id = ?
                """,
                (reason, closed_ts, closed_ts, safe),
            )
            await conn.commit()

        sqlite_sync_bridge.run(_operation, db_path=self._db_path)

    def list_active(self) -> list[dict[str, Any]]:
        self._ensure_initialized()
        async def _operation(conn: aiosqlite.Connection) -> list[Any]:
            cursor = await conn.execute(
                """
                SELECT * FROM process_leases
                WHERE status = 'active'
                ORDER BY created_at ASC
                """
            )
            return list(await cursor.fetchall())

        rows = sqlite_sync_bridge.run(_operation, db_path=self._db_path)
        return [self._row_to_payload(row) for row in rows]

    def prune_closed_before(self, *, cutoff_iso: str) -> int:
        self._ensure_initialized()
        async def _operation(conn: aiosqlite.Connection) -> int:
            cur = await conn.execute(
                """
                DELETE FROM process_leases
                WHERE status = 'closed'
                  AND COALESCE(closed_at, updated_at) < ?
                """,
                (cutoff_iso,),
            )
            await conn.commit()
            return int(cur.rowcount or 0)

        return sqlite_sync_bridge.run(_operation, db_path=self._db_path)


process_lease_store = ProcessLeaseStore()
