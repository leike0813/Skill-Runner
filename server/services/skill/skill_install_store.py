import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from server.config import config
from server.models import SkillInstallStatus


class SkillInstallStore:
    """SQLite-backed store for skill package install request lifecycle."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path(config.SYSTEM.SKILL_INSTALLS_DB)
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
                CREATE TABLE IF NOT EXISTS skill_installs (
                    request_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    skill_id TEXT,
                    version TEXT,
                    action TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await conn.commit()

    async def create_install(self, request_id: str) -> None:
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT INTO skill_installs (
                    request_id, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                (request_id, SkillInstallStatus.QUEUED.value, now, now)
            )
            await conn.commit()

    async def update_running(self, request_id: str) -> None:
        await self._update(
            request_id,
            status=SkillInstallStatus.RUNNING.value,
            error=None
        )

    async def update_succeeded(
        self,
        request_id: str,
        skill_id: str,
        version: str,
        action: str
    ) -> None:
        await self._update(
            request_id,
            status=SkillInstallStatus.SUCCEEDED.value,
            skill_id=skill_id,
            version=version,
            action=action,
            error=None
        )

    async def update_failed(self, request_id: str, error: str) -> None:
        await self._update(
            request_id,
            status=SkillInstallStatus.FAILED.value,
            error=error
        )

    async def _update(self, request_id: str, **fields: Any) -> None:
        await self._ensure_initialized()
        if not fields:
            return
        fields["updated_at"] = datetime.utcnow().isoformat()
        columns = ", ".join(f"{key} = ?" for key in fields.keys())
        values = list(fields.values()) + [request_id]
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                f"UPDATE skill_installs SET {columns} WHERE request_id = ?",
                values
            )
            await conn.commit()

    async def get_install(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM skill_installs WHERE request_id = ?",
                (request_id,)
            )
            row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)

    async def list_installs(self, limit: int = 50) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT * FROM skill_installs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,)
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]


skill_install_store = SkillInstallStore()
