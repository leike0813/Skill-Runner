from datetime import datetime
from typing import Optional

from server.services.platform import aiosqlite_compat as aiosqlite

from .run_store_database import RunStoreDatabase


class RunCacheStore:
    def __init__(self, database: RunStoreDatabase) -> None:
        self._database = database

    async def record_cache_entry(self, cache_key: str, run_id: str) -> None:
        await self._record_cache_entry(table="cache_entries", cache_key=cache_key, run_id=run_id)

    async def record_temp_cache_entry(self, cache_key: str, run_id: str) -> None:
        await self._record_cache_entry(table="temp_cache_entries", cache_key=cache_key, run_id=run_id)

    async def get_cached_run(self, cache_key: str) -> Optional[str]:
        return await self._get_cached_run(table="cache_entries", cache_key=cache_key)

    async def get_temp_cached_run(self, cache_key: str) -> Optional[str]:
        return await self._get_cached_run(table="temp_cache_entries", cache_key=cache_key)

    async def get_cached_run_for_source(self, cache_key: str, source: str) -> Optional[str]:
        if source == "temp_upload":
            return await self.get_temp_cached_run(cache_key)
        return await self.get_cached_run(cache_key)

    async def _record_cache_entry(self, table: str, cache_key: str, run_id: str) -> None:
        await self._database.ensure_initialized()
        created_at = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                f"""
                INSERT OR REPLACE INTO {table} (cache_key, run_id, status, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (cache_key, run_id, "succeeded", created_at),
            )
            await conn.commit()

    async def _get_cached_run(self, table: str, cache_key: str) -> Optional[str]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                f"SELECT run_id FROM {table} WHERE cache_key = ? AND status = ?",
                (cache_key, "succeeded"),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        return row["run_id"]
