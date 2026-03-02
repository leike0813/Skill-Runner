import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import aiosqlite

from server.config import config
from server.models import EngineUpgradeTaskStatus


class EngineUpgradeStore:
    """SQLite-backed store for engine upgrade task lifecycle."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path(config.SYSTEM.ENGINE_UPGRADES_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_lock = asyncio.Lock()
        self._initialized = False

    def _connect(self):
        return aiosqlite.connect(str(self.db_path))

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            await self._init_db()
            self._initialized = True

    async def _init_db(self) -> None:
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS engine_upgrades (
                    request_id TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    requested_engine TEXT,
                    status TEXT NOT NULL,
                    results_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await conn.commit()

    async def create_task(self, request_id: str, mode: str, requested_engine: Optional[str]) -> None:
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT INTO engine_upgrades (
                    request_id, mode, requested_engine, status, results_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    mode,
                    requested_engine,
                    EngineUpgradeTaskStatus.QUEUED.value,
                    "{}",
                    now,
                    now,
                ),
            )
            await conn.commit()

    async def update_task(
        self,
        request_id: str,
        *,
        status: Optional[EngineUpgradeTaskStatus] = None,
        results: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self._ensure_initialized()
        updates: Dict[str, Any] = {"updated_at": datetime.utcnow().isoformat()}
        if status is not None:
            updates["status"] = status.value
        if results is not None:
            updates["results_json"] = json.dumps(results, sort_keys=True)
        columns = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [request_id]
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(f"UPDATE engine_upgrades SET {columns} WHERE request_id = ?", values)
            await conn.commit()

    async def get_task(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM engine_upgrades WHERE request_id = ?",
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["results"] = json.loads(payload.pop("results_json"))
        return payload

    async def has_running_task(self) -> bool:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT request_id FROM engine_upgrades WHERE status = ? LIMIT 1",
                (EngineUpgradeTaskStatus.RUNNING.value,),
            )
            row = await cursor.fetchone()
        return row is not None


engine_upgrade_store = EngineUpgradeStore()
