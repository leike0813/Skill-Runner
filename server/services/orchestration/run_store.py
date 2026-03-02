import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from server.config import config
from server.models import InteractiveErrorCode
from server.runtime.protocol.schema_registry import (
    ProtocolSchemaViolation,
    validate_interaction_history_entry,
    validate_pending_interaction,
)


class RunStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path(config.SYSTEM.RUNS_DB)
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
                CREATE TABLE IF NOT EXISTS requests (
                    request_id TEXT PRIMARY KEY,
                    skill_id TEXT NOT NULL,
                    engine TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    parameter_json TEXT NOT NULL,
                    engine_options_json TEXT NOT NULL,
                    runtime_options_json TEXT NOT NULL,
                    input_manifest_path TEXT,
                    input_manifest_hash TEXT,
                    skill_fingerprint TEXT,
                    cache_key TEXT,
                    run_id TEXT,
                    status TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            request_info_cur = await conn.execute("PRAGMA table_info(requests)")
            existing_cols = {row["name"] for row in await request_info_cur.fetchall()}
            if "run_id" not in existing_cols:
                await conn.execute("ALTER TABLE requests ADD COLUMN run_id TEXT")
            if "input_json" not in existing_cols:
                await conn.execute("ALTER TABLE requests ADD COLUMN input_json TEXT NOT NULL DEFAULT '{}'")

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    cache_key TEXT,
                    status TEXT,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    result_path TEXT,
                    artifacts_manifest_path TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            run_info_cur = await conn.execute("PRAGMA table_info(runs)")
            run_cols = {row["name"] for row in await run_info_cur.fetchall()}
            if "cancel_requested" not in run_cols:
                await conn.execute("ALTER TABLE runs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0")
            if "recovery_state" not in run_cols:
                await conn.execute("ALTER TABLE runs ADD COLUMN recovery_state TEXT NOT NULL DEFAULT 'none'")
            if "recovered_at" not in run_cols:
                await conn.execute("ALTER TABLE runs ADD COLUMN recovered_at TEXT")
            if "recovery_reason" not in run_cols:
                await conn.execute("ALTER TABLE runs ADD COLUMN recovery_reason TEXT")

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS temp_cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS request_interactions (
                    request_id TEXT NOT NULL,
                    interaction_id INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    idempotency_key TEXT,
                    reply_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (request_id, interaction_id)
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS request_interactive_runtime (
                    request_id TEXT PRIMARY KEY,
                    effective_session_timeout_sec INTEGER,
                    session_handle_json TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await self._migrate_interactive_runtime_table(conn)
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS request_interaction_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    interaction_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_request_interactions_pending
                ON request_interactions (request_id, state)
                """
            )
            await conn.commit()

    async def _migrate_interactive_runtime_table(self, conn: aiosqlite.Connection) -> None:
        runtime_cur = await conn.execute("PRAGMA table_info(request_interactive_runtime)")
        runtime_cols = {row["name"] for row in await runtime_cur.fetchall()}
        expected_cols = {
            "request_id",
            "effective_session_timeout_sec",
            "session_handle_json",
            "updated_at",
        }
        if runtime_cols == expected_cols:
            return

        now = datetime.utcnow().isoformat()
        await conn.execute("ALTER TABLE request_interactive_runtime RENAME TO request_interactive_runtime_legacy")
        await conn.execute(
            """
            CREATE TABLE request_interactive_runtime (
                request_id TEXT PRIMARY KEY,
                effective_session_timeout_sec INTEGER,
                session_handle_json TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        legacy_cur = await conn.execute("SELECT * FROM request_interactive_runtime_legacy")
        legacy_rows = await legacy_cur.fetchall()
        for row in legacy_rows:
            row_dict = dict(row)
            request_id = row_dict.get("request_id")
            if not isinstance(request_id, str) or not request_id:
                continue
            timeout_obj = row_dict.get("effective_session_timeout_sec")
            timeout_value: int | None = None
            if timeout_obj is not None:
                try:
                    timeout_value = int(timeout_obj)
                except (TypeError, ValueError, OverflowError):
                    timeout_value = None
            if timeout_value is None:
                profile_raw = row_dict.get("profile_json")
                if isinstance(profile_raw, str) and profile_raw:
                    try:
                        profile = json.loads(profile_raw)
                    except (json.JSONDecodeError, TypeError):
                        profile = {}
                    timeout_from_profile = profile.get("session_timeout_sec")
                    if timeout_from_profile is not None:
                        try:
                            timeout_value = int(timeout_from_profile)
                        except (TypeError, ValueError, OverflowError):
                            timeout_value = None
            if timeout_value is None:
                timeout_value = int(config.SYSTEM.SESSION_TIMEOUT_SEC)
            handle_obj = row_dict.get("session_handle_json")
            handle_json = handle_obj if isinstance(handle_obj, str) else None
            updated_at_obj = row_dict.get("updated_at")
            updated_at = updated_at_obj if isinstance(updated_at_obj, str) and updated_at_obj else now
            await conn.execute(
                """
                INSERT OR REPLACE INTO request_interactive_runtime (
                    request_id, effective_session_timeout_sec, session_handle_json, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                (request_id, timeout_value, handle_json, updated_at),
            )
        await conn.execute("DROP TABLE request_interactive_runtime_legacy")

    async def create_request(
        self,
        request_id: str,
        skill_id: str,
        engine: str,
        parameter: Dict[str, Any],
        engine_options: Dict[str, Any],
        runtime_options: Dict[str, Any],
        input_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self._ensure_initialized()
        created_at = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT INTO requests (
                    request_id, skill_id, engine, input_json, parameter_json,
                    engine_options_json, runtime_options_json, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    skill_id,
                    engine,
                    json.dumps(input_data or {}, sort_keys=True),
                    json.dumps(parameter, sort_keys=True),
                    json.dumps(engine_options, sort_keys=True),
                    json.dumps(runtime_options, sort_keys=True),
                    "created",
                    created_at,
                ),
            )
            await conn.commit()

    async def update_request_manifest(self, request_id: str, manifest_path: str, manifest_hash: str) -> None:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE requests
                SET input_manifest_path = ?, input_manifest_hash = ?
                WHERE request_id = ?
                """,
                (manifest_path, manifest_hash, request_id),
            )
            await conn.commit()

    async def update_request_cache_key(self, request_id: str, cache_key: str, skill_fingerprint: str) -> None:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE requests
                SET cache_key = ?, skill_fingerprint = ?, status = ?
                WHERE request_id = ?
                """,
                (cache_key, skill_fingerprint, "ready", request_id),
            )
            await conn.commit()

    async def update_request_run_id(self, request_id: str, run_id: str) -> None:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE requests
                SET run_id = ?, status = ?
                WHERE request_id = ?
                """,
                (run_id, "running", request_id),
            )
            await conn.commit()

    async def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM requests WHERE request_id = ?", (request_id,))
            row = await cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data["input"] = json.loads(data["input_json"])
        data["parameter"] = json.loads(data["parameter_json"])
        data["engine_options"] = json.loads(data["engine_options_json"])
        data["runtime_options"] = json.loads(data["runtime_options_json"])
        return data

    async def get_request_with_run(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT
                    req.request_id AS request_id,
                    req.skill_id AS skill_id,
                    req.engine AS engine,
                    req.run_id AS run_id,
                    req.runtime_options_json AS runtime_options_json,
                    req.created_at AS request_created_at,
                    run.status AS run_status,
                    run.created_at AS run_created_at,
                    run.recovery_state AS recovery_state,
                    run.recovered_at AS recovered_at,
                    run.recovery_reason AS recovery_reason
                FROM requests req
                LEFT JOIN runs run ON req.run_id = run.run_id
                WHERE req.request_id = ?
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        runtime_options_raw = data.pop("runtime_options_json", "{}")
        try:
            data["runtime_options"] = json.loads(runtime_options_raw or "{}")
        except (json.JSONDecodeError, TypeError):
            data["runtime_options"] = {}
        return data

    async def get_request_by_run_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM requests WHERE run_id = ?", (run_id,))
            row = await cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data["input"] = json.loads(data["input_json"])
        data["parameter"] = json.loads(data["parameter_json"])
        data["engine_options"] = json.loads(data["engine_options_json"])
        data["runtime_options"] = json.loads(data["runtime_options_json"])
        return data

    async def list_requests_with_runs(self, limit: int = 200) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        safe_limit = max(1, min(int(limit), 1000))
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT
                    req.request_id AS request_id,
                    req.skill_id AS skill_id,
                    req.engine AS engine,
                    req.run_id AS run_id,
                    req.created_at AS request_created_at,
                    run.status AS run_status,
                    run.created_at AS run_created_at,
                    run.recovery_state AS recovery_state,
                    run.recovered_at AS recovered_at,
                    run.recovery_reason AS recovery_reason
                FROM requests req
                LEFT JOIN runs run ON req.run_id = run.run_id
                WHERE req.run_id IS NOT NULL
                ORDER BY req.created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def create_run(
        self,
        run_id: str,
        cache_key: Optional[str],
        status: str,
        result_path: str = "",
        artifacts_manifest_path: str = "",
    ) -> None:
        await self._ensure_initialized()
        created_at = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT INTO runs (
                    run_id, cache_key, status, cancel_requested, result_path, artifacts_manifest_path, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, cache_key, status, 0, result_path, artifacts_manifest_path, created_at),
            )
            await conn.commit()

    async def update_run_status(self, run_id: str, status: str, result_path: Optional[str] = None) -> None:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            if result_path is not None:
                await conn.execute(
                    "UPDATE runs SET status = ?, result_path = ? WHERE run_id = ?",
                    (status, result_path, run_id),
                )
            else:
                await conn.execute(
                    "UPDATE runs SET status = ? WHERE run_id = ?",
                    (status, run_id),
                )
            await conn.commit()

    async def record_cache_entry(self, cache_key: str, run_id: str) -> None:
        await self._record_cache_entry(table="cache_entries", cache_key=cache_key, run_id=run_id)

    async def record_temp_cache_entry(self, cache_key: str, run_id: str) -> None:
        await self._record_cache_entry(table="temp_cache_entries", cache_key=cache_key, run_id=run_id)

    async def _record_cache_entry(self, table: str, cache_key: str, run_id: str) -> None:
        await self._ensure_initialized()
        created_at = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                f"""
                INSERT OR REPLACE INTO {table} (cache_key, run_id, status, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (cache_key, run_id, "succeeded", created_at),
            )
            await conn.commit()

    async def get_cached_run(self, cache_key: str) -> Optional[str]:
        return await self._get_cached_run(table="cache_entries", cache_key=cache_key)

    async def get_temp_cached_run(self, cache_key: str) -> Optional[str]:
        return await self._get_cached_run(table="temp_cache_entries", cache_key=cache_key)

    async def _get_cached_run(self, table: str, cache_key: str) -> Optional[str]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                f"SELECT run_id FROM {table} WHERE cache_key = ? AND status = ?",
                (cache_key, "succeeded"),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        return row["run_id"]

    async def list_runs_for_cleanup(self, retention_days: int) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        if retention_days <= 0:
            return []
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        candidates = []
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT run_id, status, created_at FROM runs")
            rows = await cursor.fetchall()
        for row in rows:
            status = row["status"]
            if status in ("running", "queued", "waiting_user"):
                continue
            if status == "failed":
                candidates.append(dict(row))
                continue
            created_at = row["created_at"]
            try:
                created_ts = datetime.fromisoformat(created_at)
            except ValueError:
                candidates.append(dict(row))
                continue
            if created_ts <= cutoff:
                candidates.append(dict(row))
        return candidates

    async def delete_run_records(self, run_id: str) -> List[str]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            request_cur = await conn.execute("SELECT request_id FROM requests WHERE run_id = ?", (run_id,))
            request_rows = await request_cur.fetchall()
            request_ids = [row["request_id"] for row in request_rows]
            if request_ids:
                placeholders = ",".join("?" for _ in request_ids)
                await conn.execute(
                    f"DELETE FROM request_interactions WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                )
                await conn.execute(
                    f"DELETE FROM request_interactive_runtime WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                )
                await conn.execute(
                    f"DELETE FROM request_interaction_history WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                )
            await conn.execute("DELETE FROM requests WHERE run_id = ?", (run_id,))
            await conn.execute("DELETE FROM cache_entries WHERE run_id = ?", (run_id,))
            await conn.execute("DELETE FROM temp_cache_entries WHERE run_id = ?", (run_id,))
            await conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
            await conn.commit()
        return request_ids

    async def list_request_ids(self) -> List[str]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT request_id FROM requests")
            rows = await cursor.fetchall()
        return [row["request_id"] for row in rows]

    async def clear_all(self) -> Dict[str, int]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            run_rows_cur = await conn.execute("SELECT run_id FROM runs")
            request_rows_cur = await conn.execute("SELECT request_id FROM requests")
            cache_rows_cur = await conn.execute("SELECT cache_key FROM cache_entries")
            temp_cache_rows_cur = await conn.execute("SELECT cache_key FROM temp_cache_entries")
            run_rows = await run_rows_cur.fetchall()
            request_rows = await request_rows_cur.fetchall()
            cache_rows = await cache_rows_cur.fetchall()
            temp_cache_rows = await temp_cache_rows_cur.fetchall()
            run_count = len(run_rows)
            request_count = len(request_rows)
            cache_count = len(cache_rows) + len(temp_cache_rows)
            await conn.execute("DELETE FROM request_interactions")
            await conn.execute("DELETE FROM request_interactive_runtime")
            await conn.execute("DELETE FROM request_interaction_history")
            await conn.execute("DELETE FROM cache_entries")
            await conn.execute("DELETE FROM temp_cache_entries")
            await conn.execute("DELETE FROM runs")
            await conn.execute("DELETE FROM requests")
            await conn.commit()
        return {"runs": run_count, "requests": request_count, "cache_entries": cache_count}

    async def list_active_run_ids(self) -> List[str]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT run_id FROM runs WHERE status IN (?, ?, ?)",
                ("queued", "running", "waiting_user"),
            )
            rows = await cursor.fetchall()
        return [row["run_id"] for row in rows if row["run_id"]]

    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = await cursor.fetchone()
        if not row:
            return None
        return dict(row)

    async def list_incomplete_runs(self) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT
                    req.request_id AS request_id,
                    req.run_id AS run_id,
                    req.skill_id AS skill_id,
                    req.engine AS engine,
                    req.runtime_options_json AS runtime_options_json,
                    run.status AS run_status,
                    run.recovery_state AS recovery_state,
                    run.recovered_at AS recovered_at,
                    run.recovery_reason AS recovery_reason,
                    ir.effective_session_timeout_sec AS effective_session_timeout_sec,
                    ir.session_handle_json AS session_handle_json,
                    ir.updated_at AS interactive_runtime_updated_at
                FROM requests req
                JOIN runs run ON req.run_id = run.run_id
                LEFT JOIN request_interactive_runtime ir ON req.request_id = ir.request_id
                WHERE run.status IN ('queued', 'running', 'waiting_user')
                ORDER BY req.created_at ASC
                """
            )
            rows = await cursor.fetchall()
        records: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            runtime_options_json = item.pop("runtime_options_json", "{}")
            session_handle_json = item.pop("session_handle_json", None)
            timeout_obj = item.get("effective_session_timeout_sec")
            try:
                item["runtime_options"] = json.loads(runtime_options_json or "{}")
            except (json.JSONDecodeError, TypeError):
                item["runtime_options"] = {}
            if timeout_obj is None:
                item["interactive_session_config"] = None
            else:
                try:
                    item["interactive_session_config"] = {"session_timeout_sec": int(timeout_obj)}
                except (TypeError, ValueError, OverflowError):
                    item["interactive_session_config"] = None
            try:
                item["session_handle"] = json.loads(session_handle_json) if session_handle_json else None
            except (json.JSONDecodeError, TypeError):
                item["session_handle"] = None
            records.append(item)
        return records

    async def set_recovery_info(
        self,
        run_id: str,
        *,
        recovery_state: str,
        recovery_reason: Optional[str] = None,
        recovered_at: Optional[str] = None,
    ) -> None:
        await self._ensure_initialized()
        recovered_ts = recovered_at or datetime.utcnow().isoformat()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE runs
                SET recovery_state = ?, recovered_at = ?, recovery_reason = ?
                WHERE run_id = ?
                """,
                (recovery_state, recovered_ts, recovery_reason, run_id),
            )
            await conn.commit()

    async def get_recovery_info(self, run_id: str) -> Dict[str, Any]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT recovery_state, recovered_at, recovery_reason
                FROM runs
                WHERE run_id = ?
                """,
                (run_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return {
                "recovery_state": "none",
                "recovered_at": None,
                "recovery_reason": None,
            }
        return {
            "recovery_state": row["recovery_state"] or "none",
            "recovered_at": row["recovered_at"],
            "recovery_reason": row["recovery_reason"],
        }

    async def set_cancel_requested(self, run_id: str, requested: bool = True) -> bool:
        await self._ensure_initialized()
        next_value = 1 if requested else 0
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT cancel_requested FROM runs WHERE run_id = ?", (run_id,))
            row = await cursor.fetchone()
            if not row:
                return False
            current_value = int(row["cancel_requested"] or 0)
            await conn.execute("UPDATE runs SET cancel_requested = ? WHERE run_id = ?", (next_value, run_id))
            await conn.commit()
        return current_value != next_value

    async def is_cancel_requested(self, run_id: str) -> bool:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("SELECT cancel_requested FROM runs WHERE run_id = ?", (run_id,))
            row = await cursor.fetchone()
        if not row:
            return False
        return int(row["cancel_requested"] or 0) == 1

    async def _upsert_interactive_runtime(
        self,
        request_id: str,
        *,
        effective_session_timeout_sec: Optional[int] = None,
        session_handle_json: Optional[str] = None,
    ) -> None:
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT effective_session_timeout_sec, session_handle_json
                FROM request_interactive_runtime
                WHERE request_id = ?
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
            current = dict(row) if row else {}
            await conn.execute(
                """
                INSERT OR REPLACE INTO request_interactive_runtime (
                    request_id, effective_session_timeout_sec, session_handle_json, updated_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    request_id,
                    (
                        effective_session_timeout_sec
                        if effective_session_timeout_sec is not None
                        else current.get("effective_session_timeout_sec")
                    ),
                    session_handle_json
                    if session_handle_json is not None
                    else current.get("session_handle_json"),
                    now,
                ),
            )
            await conn.commit()

    async def set_interactive_profile(self, request_id: str, profile: Dict[str, Any]) -> None:
        timeout = profile.get("session_timeout_sec")
        if timeout is None:
            timeout = config.SYSTEM.SESSION_TIMEOUT_SEC
        await self._upsert_interactive_runtime(request_id, effective_session_timeout_sec=int(timeout))

    async def set_effective_session_timeout(self, request_id: str, timeout_sec: int) -> None:
        await self._upsert_interactive_runtime(
            request_id,
            effective_session_timeout_sec=int(timeout_sec),
        )

    async def get_interactive_profile(self, request_id: str) -> Optional[Dict[str, Any]]:
        timeout = await self.get_effective_session_timeout(request_id)
        if timeout is None:
            return None
        return {"session_timeout_sec": int(timeout)}

    async def get_effective_session_timeout(self, request_id: str) -> Optional[int]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT effective_session_timeout_sec
                FROM request_interactive_runtime
                WHERE request_id = ?
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row or row["effective_session_timeout_sec"] is None:
            return None
        return int(row["effective_session_timeout_sec"])

    async def set_engine_session_handle(self, request_id: str, handle: Dict[str, Any]) -> None:
        await self._upsert_interactive_runtime(
            request_id,
            session_handle_json=json.dumps(handle, sort_keys=True),
        )

    async def get_engine_session_handle(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT session_handle_json
                FROM request_interactive_runtime
                WHERE request_id = ?
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row or row["session_handle_json"] is None:
            return None
        return json.loads(row["session_handle_json"])

    async def clear_engine_session_handle(self, request_id: str) -> None:
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE request_interactive_runtime
                SET session_handle_json = NULL, updated_at = ?
                WHERE request_id = ?
                """,
                (now, request_id),
            )
            await conn.commit()

    async def append_interaction_history(
        self,
        request_id: str,
        interaction_id: int,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        entry = {
            "interaction_id": int(interaction_id),
            "event_type": event_type,
            "payload": payload,
            "created_at": now,
        }
        try:
            validate_interaction_history_entry(entry)
        except ProtocolSchemaViolation as exc:
            raise ValueError(
                f"{InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value}: {exc}"
            ) from exc
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT INTO request_interaction_history (
                    request_id, interaction_id, event_type, payload_json, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    interaction_id,
                    event_type,
                    json.dumps(payload, sort_keys=True),
                    now,
                ),
            )
            await conn.commit()

    async def clear_pending_interaction(self, request_id: str) -> None:
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                UPDATE request_interactions
                SET state = 'consumed', updated_at = ?
                WHERE request_id = ? AND state = 'pending'
                """,
                (now, request_id),
            )
            await conn.commit()

    async def list_interaction_history(self, request_id: str) -> List[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT interaction_id, event_type, payload_json, created_at
                FROM request_interaction_history
                WHERE request_id = ?
                ORDER BY id ASC
                """,
                (request_id,),
            )
            rows = await cursor.fetchall()
        history: List[Dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "Skipping interaction history row with invalid JSON: request_id=%s interaction_id=%s",
                    request_id,
                    row["interaction_id"],
                )
                continue
            item = {
                "interaction_id": row["interaction_id"],
                "event_type": row["event_type"],
                "payload": payload,
                "created_at": row["created_at"],
            }
            try:
                validate_interaction_history_entry(item)
            except ProtocolSchemaViolation as exc:
                logger.warning(
                    "Skipping incompatible interaction history row: request_id=%s interaction_id=%s detail=%s",
                    request_id,
                    row["interaction_id"],
                    str(exc),
                )
                continue
            history.append(item)
        return history

    async def set_pending_interaction(self, request_id: str, payload: Dict[str, Any]) -> None:
        await self._ensure_initialized()
        try:
            validate_pending_interaction(payload)
        except ProtocolSchemaViolation as exc:
            raise ValueError(
                f"{InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value}: {exc}"
            ) from exc
        interaction_id = int(payload["interaction_id"])
        now = datetime.utcnow().isoformat()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT OR REPLACE INTO request_interactions (
                    request_id, interaction_id, payload_json, state,
                    idempotency_key, reply_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    interaction_id,
                    json.dumps(payload, sort_keys=True),
                    "pending",
                    None,
                    None,
                    now,
                    now,
                ),
            )
            await conn.commit()

    async def get_pending_interaction(self, request_id: str) -> Optional[Dict[str, Any]]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT payload_json
                FROM request_interactions
                WHERE request_id = ? AND state = 'pending'
                ORDER BY interaction_id DESC
                LIMIT 1
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid pending interaction JSON ignored: request_id=%s", request_id)
            return None
        try:
            validate_pending_interaction(payload)
        except ProtocolSchemaViolation as exc:
            logger.warning(
                "Invalid pending interaction payload ignored: request_id=%s detail=%s",
                request_id,
                str(exc),
            )
            return None
        return payload

    async def get_interaction_count(self, request_id: str) -> int:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM request_interactions
                WHERE request_id = ?
                """,
                (request_id,),
            )
            row = await cursor.fetchone()
        if not row:
            return 0
        return int(row["count"] or 0)

    async def get_auto_decision_stats(self, request_id: str) -> Dict[str, Any]:
        history = await self.list_interaction_history(request_id)
        auto_decision_count = 0
        last_auto_decision_at: Optional[str] = None
        for item in history:
            if item.get("event_type") != "reply":
                continue
            payload_obj = item.get("payload")
            if not isinstance(payload_obj, dict):
                continue
            if payload_obj.get("resolution_mode") != "auto_decide_timeout":
                continue
            auto_decision_count += 1
            resolved_at_obj = payload_obj.get("resolved_at")
            if isinstance(resolved_at_obj, str) and resolved_at_obj:
                if last_auto_decision_at is None or resolved_at_obj > last_auto_decision_at:
                    last_auto_decision_at = resolved_at_obj
        return {
            "auto_decision_count": auto_decision_count,
            "last_auto_decision_at": last_auto_decision_at,
        }

    async def get_interaction_reply(
        self, request_id: str, interaction_id: int, idempotency_key: str
    ) -> Optional[Any]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT reply_json
                FROM request_interactions
                WHERE request_id = ? AND interaction_id = ? AND idempotency_key = ?
                """,
                (request_id, interaction_id, idempotency_key),
            )
            row = await cursor.fetchone()
        if not row or row["reply_json"] is None:
            return None
        return json.loads(row["reply_json"])

    async def consume_interaction_reply(self, request_id: str, interaction_id: int) -> Optional[Any]:
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT state, reply_json
                FROM request_interactions
                WHERE request_id = ? AND interaction_id = ?
                """,
                (request_id, interaction_id),
            )
            row = await cursor.fetchone()
            if not row or row["state"] != "answered" or row["reply_json"] is None:
                return None
            await conn.execute(
                """
                UPDATE request_interactions
                SET state = ?, updated_at = ?
                WHERE request_id = ? AND interaction_id = ?
                """,
                ("consumed", datetime.utcnow().isoformat(), request_id, interaction_id),
            )
            await conn.commit()
            return json.loads(row["reply_json"])

    async def submit_interaction_reply(
        self,
        request_id: str,
        interaction_id: int,
        response: Any,
        idempotency_key: Optional[str],
    ) -> str:
        """
        Returns one of: accepted | idempotent | stale | idempotency_conflict.
        """
        await self._ensure_initialized()
        async with self._connect() as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                SELECT state, idempotency_key, reply_json
                FROM request_interactions
                WHERE request_id = ? AND interaction_id = ?
                """,
                (request_id, interaction_id),
            )
            row = await cursor.fetchone()
            if not row:
                return "stale"

            state = row["state"]
            existing_key = row["idempotency_key"]
            existing_reply = json.loads(row["reply_json"]) if row["reply_json"] is not None else None
            if state != "pending":
                if idempotency_key and existing_key == idempotency_key:
                    if existing_reply == response:
                        return "idempotent"
                    return "idempotency_conflict"
                return "stale"

            now = datetime.utcnow().isoformat()
            await conn.execute(
                """
                UPDATE request_interactions
                SET state = ?, idempotency_key = ?, reply_json = ?, updated_at = ?
                WHERE request_id = ? AND interaction_id = ?
                """,
                (
                    "answered",
                    idempotency_key,
                    json.dumps(response, sort_keys=True),
                    now,
                    request_id,
                    interaction_id,
                ),
            )
            await conn.commit()
            return "accepted"


run_store = RunStore()
logger = logging.getLogger(__name__)
