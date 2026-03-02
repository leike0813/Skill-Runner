import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from server.config import config
from server.models import RunStatus


class TempSkillRunStore:
    """SQLite-backed lifecycle store for /v1/temp-skill-runs."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path(config.SYSTEM.TEMP_SKILL_RUNS_DB)
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
                CREATE TABLE IF NOT EXISTS temp_skill_runs (
                    request_id TEXT PRIMARY KEY,
                    engine TEXT NOT NULL,
                    parameter_json TEXT NOT NULL,
                    model TEXT,
                    engine_options_json TEXT NOT NULL,
                    runtime_options_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    skill_id TEXT,
                    run_id TEXT,
                    error TEXT,
                    skill_package_path TEXT,
                    staged_skill_dir TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await conn.commit()

    async def create_request(
        self,
        request_id: str,
        engine: str,
        parameter: Dict[str, Any],
        model: Optional[str],
        engine_options: Dict[str, Any],
        runtime_options: Dict[str, Any]
    ) -> None:
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT INTO temp_skill_runs (
                    request_id, engine, parameter_json, model,
                    engine_options_json, runtime_options_json, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    engine,
                    json.dumps(parameter, sort_keys=True),
                    model,
                    json.dumps(engine_options, sort_keys=True),
                    json.dumps(runtime_options, sort_keys=True),
                    RunStatus.QUEUED.value,
                    now,
                    now,
                ),
            )
            await conn.commit()

    async def update_staged_skill(
        self,
        request_id: str,
        *,
        skill_id: str,
        skill_package_path: str,
        staged_skill_dir: str
    ) -> None:
        await self._update(
            request_id,
            skill_id=skill_id,
            skill_package_path=skill_package_path,
            staged_skill_dir=staged_skill_dir,
        )

    async def update_run_started(self, request_id: str, run_id: str) -> None:
        await self._update(request_id, run_id=run_id, status=RunStatus.RUNNING.value, error=None)

    async def bind_cached_run(self, request_id: str, run_id: str) -> None:
        await self._update(request_id, run_id=run_id, status=RunStatus.SUCCEEDED.value, error=None)

    async def update_status(self, request_id: str, status: RunStatus, error: Optional[str] = None) -> None:
        await self._update(request_id, status=status.value, error=error)

    async def clear_temp_paths(self, request_id: str) -> None:
        await self._update(request_id, skill_package_path=None, staged_skill_dir=None)

    async def _update(self, request_id: str, **fields: Any) -> None:
        await self._ensure_initialized()
        if not fields:
            return
        fields["updated_at"] = datetime.utcnow().isoformat()
        columns = ", ".join(f"{k} = ?" for k in fields.keys())
        values = list(fields.values()) + [request_id]
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(f"UPDATE temp_skill_runs SET {columns} WHERE request_id = ?", values)
            await conn.commit()

    async def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM temp_skill_runs WHERE request_id = ?",
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data["parameter"] = json.loads(data["parameter_json"])
        data["engine_options"] = json.loads(data["engine_options_json"])
        data["runtime_options"] = json.loads(data["runtime_options_json"])
        return data

    async def list_orphan_candidates(self, retention_hours: int) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        cutoff = datetime.utcnow() - timedelta(hours=max(retention_hours, 0))
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT request_id, status, run_id, skill_package_path, staged_skill_dir, updated_at
                FROM temp_skill_runs
                WHERE skill_package_path IS NOT NULL OR staged_skill_dir IS NOT NULL
                """
            )
            rows = await cursor.fetchall()
        candidates: List[Dict[str, Any]] = []
        for row in rows:
            status = row["status"]
            if status in (RunStatus.RUNNING.value, RunStatus.QUEUED.value):
                continue
            updated_at = row["updated_at"]
            try:
                updated = datetime.fromisoformat(updated_at)
            except ValueError:
                candidates.append(dict(row))
                continue
            if updated <= cutoff:
                candidates.append(dict(row))
        return candidates


temp_skill_run_store = TempSkillRunStore()
