import json
from datetime import datetime
from typing import Any, Dict, List, Optional

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
        _ = source
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

    async def upsert_skill_package_identity(
        self,
        *,
        skill_id: str,
        skill_package_hash: str,
        source: str,
        skill_path: str,
        manifest: Dict[str, Any],
    ) -> None:
        await self._database.ensure_initialized()
        updated_at = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT OR REPLACE INTO skill_package_identities (
                    skill_id, skill_package_hash, source, skill_path, manifest_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    skill_id,
                    skill_package_hash,
                    source,
                    skill_path,
                    json.dumps(manifest, sort_keys=True),
                    updated_at,
                ),
            )
            await conn.commit()

    async def get_skill_package_identity(self, skill_id: str) -> Optional[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM skill_package_identities WHERE skill_id = ?",
                (skill_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data["manifest"] = json.loads(data.pop("manifest_json") or "{}")
        return data

    async def upsert_temp_skill_package_cache(
        self,
        *,
        skill_package_hash: str,
        skill_id: str,
        manifest: Dict[str, Any],
        snapshot_path: str,
        expires_at: str,
    ) -> None:
        await self._database.ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT INTO temp_skill_package_cache (
                    skill_package_hash, skill_id, manifest_json, snapshot_path,
                    created_at, last_accessed_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(skill_package_hash) DO UPDATE SET
                    skill_id = excluded.skill_id,
                    manifest_json = excluded.manifest_json,
                    snapshot_path = excluded.snapshot_path,
                    last_accessed_at = excluded.last_accessed_at,
                    expires_at = excluded.expires_at
                """,
                (
                    skill_package_hash,
                    skill_id,
                    json.dumps(manifest, sort_keys=True),
                    snapshot_path,
                    now,
                    now,
                    expires_at,
                ),
            )
            await conn.commit()

    async def get_temp_skill_package_cache(self, skill_package_hash: str) -> Optional[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM temp_skill_package_cache WHERE skill_package_hash = ?",
                (skill_package_hash,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data["manifest"] = json.loads(data.pop("manifest_json") or "{}")
        return data

    async def touch_temp_skill_package_cache(self, skill_package_hash: str, *, expires_at: str) -> None:
        await self._database.ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE temp_skill_package_cache
                SET last_accessed_at = ?, expires_at = ?
                WHERE skill_package_hash = ?
                """,
                (now, expires_at, skill_package_hash),
            )
            await conn.commit()

    async def list_expired_temp_skill_package_cache(self, *, now_iso: str) -> List[Dict[str, Any]]:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM temp_skill_package_cache WHERE expires_at <= ?",
                (now_iso,),
            )
            rows = await cursor.fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["manifest"] = json.loads(data.pop("manifest_json") or "{}")
            result.append(data)
        return result

    async def delete_temp_skill_package_cache(self, skill_package_hash: str) -> None:
        await self._database.ensure_initialized()
        async with self._database.connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                "DELETE FROM temp_skill_package_cache WHERE skill_package_hash = ?",
                (skill_package_hash,),
            )
            await conn.commit()
