import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.config import config
from server.models import SkillInstallStatus
from server.services.platform import aiosqlite_compat as aiosqlite


class SkillInstallStore:
    """SQLite-backed store for skill package install request lifecycle."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path(config.SYSTEM.RUNS_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_lock = asyncio.Lock()
        self._initialized = False

    def _connect(self):
        return aiosqlite.connect(str(self.db_path))

    async def _ensure_initialized(self) -> None:
        if self._initialized and not self.db_path.exists():
            self._initialized = False
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized and not self.db_path.exists():
                self._initialized = False
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
        await self._migrate_legacy_skill_installs_if_needed()

    async def _migrate_legacy_skill_installs_if_needed(self) -> None:
        legacy_path = Path(config.SYSTEM.SKILL_INSTALLS_DB)
        if legacy_path.resolve() == self.db_path.resolve():
            return
        if not legacy_path.exists():
            return
        if not legacy_path.is_file():
            return
        try:
            async with aiosqlite.connect(str(legacy_path)) as legacy_conn:
                legacy_conn.row_factory = aiosqlite.Row
                cur = await legacy_conn.execute("SELECT * FROM skill_installs")
                rows = await cur.fetchall()
        except (OSError, RuntimeError, ValueError):
            return
        if not rows:
            return
        async with self._connect() as target_conn:
            await target_conn.execute(
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
            for row in rows:
                await target_conn.execute(
                    """
                    INSERT OR IGNORE INTO skill_installs (
                        request_id, status, skill_id, version, action, error, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["request_id"],
                        row["status"],
                        row["skill_id"],
                        row["version"],
                        row["action"],
                        row["error"],
                        row["created_at"],
                        row["updated_at"],
                    ),
                )
            await target_conn.commit()

    async def _execute(self, sql: str, params: tuple[Any, ...]) -> None:
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(sql, params)
            await conn.commit()

    async def _fetchone(self, sql: str, params: tuple[Any, ...]) -> Optional[Dict[str, Any]]:
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, params)
            row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def _fetchall(self, sql: str, params: tuple[Any, ...]) -> List[Dict[str, Any]]:
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, params)
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def create_install(self, request_id: str) -> None:
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        await self._execute(
            """
            INSERT INTO skill_installs (
                request_id, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?)
            """,
            (request_id, SkillInstallStatus.QUEUED.value, now, now),
        )

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
        values = tuple(list(fields.values()) + [request_id])
        await self._execute(
            f"UPDATE skill_installs SET {columns} WHERE request_id = ?",
            values,
        )

    async def get_install(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        return await self._fetchone(
            "SELECT * FROM skill_installs WHERE request_id = ?",
            (request_id,),
        )

    async def list_installs(self, limit: int = 50) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        return await self._fetchall(
            """
            SELECT * FROM skill_installs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )


skill_install_store = SkillInstallStore()
