import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import config
from ..models import InteractiveErrorCode
from .protocol_schema_registry import (
    ProtocolSchemaViolation,
    validate_interaction_history_entry,
    validate_pending_interaction,
)


class RunStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path(config.SYSTEM.RUNS_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
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
            existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(requests)").fetchall()}
            if "run_id" not in existing_cols:
                conn.execute("ALTER TABLE requests ADD COLUMN run_id TEXT")
            if "input_json" not in existing_cols:
                conn.execute("ALTER TABLE requests ADD COLUMN input_json TEXT NOT NULL DEFAULT '{}'")
            conn.execute(
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
            run_cols = {
                row["name"] for row in conn.execute("PRAGMA table_info(runs)").fetchall()
            }
            if "cancel_requested" not in run_cols:
                conn.execute(
                    "ALTER TABLE runs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0"
                )
            if "recovery_state" not in run_cols:
                conn.execute(
                    "ALTER TABLE runs ADD COLUMN recovery_state TEXT NOT NULL DEFAULT 'none'"
                )
            if "recovered_at" not in run_cols:
                conn.execute(
                    "ALTER TABLE runs ADD COLUMN recovered_at TEXT"
                )
            if "recovery_reason" not in run_cols:
                conn.execute(
                    "ALTER TABLE runs ADD COLUMN recovery_reason TEXT"
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS temp_cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS request_interactive_runtime (
                    request_id TEXT PRIMARY KEY,
                    effective_session_timeout_sec INTEGER,
                    session_handle_json TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._migrate_interactive_runtime_table(conn)
            conn.execute(
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
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_request_interactions_pending
                ON request_interactions (request_id, state)
                """
            )

    def _migrate_interactive_runtime_table(self, conn: sqlite3.Connection) -> None:
        runtime_cols = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(request_interactive_runtime)"
            ).fetchall()
        }
        expected_cols = {
            "request_id",
            "effective_session_timeout_sec",
            "session_handle_json",
            "updated_at",
        }
        if runtime_cols == expected_cols:
            return
        now = datetime.utcnow().isoformat()
        conn.execute(
            "ALTER TABLE request_interactive_runtime RENAME TO request_interactive_runtime_legacy"
        )
        conn.execute(
            """
            CREATE TABLE request_interactive_runtime (
                request_id TEXT PRIMARY KEY,
                effective_session_timeout_sec INTEGER,
                session_handle_json TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        legacy_rows = conn.execute(
            "SELECT * FROM request_interactive_runtime_legacy"
        ).fetchall()
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
                except Exception:
                    timeout_value = None
            if timeout_value is None:
                profile_raw = row_dict.get("profile_json")
                if isinstance(profile_raw, str) and profile_raw:
                    try:
                        profile = json.loads(profile_raw)
                    except Exception:
                        profile = {}
                    timeout_from_profile = profile.get("session_timeout_sec")
                    if timeout_from_profile is not None:
                        try:
                            timeout_value = int(timeout_from_profile)
                        except Exception:
                            timeout_value = None
            if timeout_value is None:
                timeout_value = int(config.SYSTEM.SESSION_TIMEOUT_SEC)
            handle_obj = row_dict.get("session_handle_json")
            handle_json = handle_obj if isinstance(handle_obj, str) else None
            updated_at_obj = row_dict.get("updated_at")
            updated_at = updated_at_obj if isinstance(updated_at_obj, str) and updated_at_obj else now
            conn.execute(
                """
                INSERT OR REPLACE INTO request_interactive_runtime (
                    request_id, effective_session_timeout_sec, session_handle_json, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                (request_id, timeout_value, handle_json, updated_at),
            )
        conn.execute("DROP TABLE request_interactive_runtime_legacy")

    def create_request(
        self,
        request_id: str,
        skill_id: str,
        engine: str,
        parameter: Dict[str, Any],
        engine_options: Dict[str, Any],
        runtime_options: Dict[str, Any],
        input_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        created_at = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
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
                    created_at
                )
            )

    def update_request_manifest(self, request_id: str, manifest_path: str, manifest_hash: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE requests
                SET input_manifest_path = ?, input_manifest_hash = ?
                WHERE request_id = ?
                """,
                (manifest_path, manifest_hash, request_id)
            )

    def update_request_cache_key(self, request_id: str, cache_key: str, skill_fingerprint: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE requests
                SET cache_key = ?, skill_fingerprint = ?, status = ?
                WHERE request_id = ?
                """,
                (cache_key, skill_fingerprint, "ready", request_id)
            )

    def update_request_run_id(self, request_id: str, run_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE requests
                SET run_id = ?, status = ?
                WHERE request_id = ?
                """,
                (run_id, "running", request_id)
            )

    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM requests WHERE request_id = ?",
                (request_id,)
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["input"] = json.loads(data["input_json"])
        data["parameter"] = json.loads(data["parameter_json"])
        data["engine_options"] = json.loads(data["engine_options_json"])
        data["runtime_options"] = json.loads(data["runtime_options_json"])
        return data

    def get_request_with_run(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
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
                WHERE req.request_id = ?
                """,
                (request_id,),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def get_request_by_run_id(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM requests WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["input"] = json.loads(data["input_json"])
        data["parameter"] = json.loads(data["parameter_json"])
        data["engine_options"] = json.loads(data["engine_options_json"])
        data["runtime_options"] = json.loads(data["runtime_options_json"])
        return data

    def list_requests_with_runs(self, limit: int = 200) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 1000))
        with self._connect() as conn:
            rows = conn.execute(
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
            ).fetchall()
        return [dict(row) for row in rows]

    def create_run(
        self,
        run_id: str,
        cache_key: Optional[str],
        status: str,
        result_path: str = "",
        artifacts_manifest_path: str = "",
    ) -> None:
        created_at = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, cache_key, status, cancel_requested, result_path, artifacts_manifest_path, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, cache_key, status, 0, result_path, artifacts_manifest_path, created_at)
            )

    def update_run_status(self, run_id: str, status: str, result_path: Optional[str] = None) -> None:
        with self._connect() as conn:
            if result_path is not None:
                conn.execute(
                    "UPDATE runs SET status = ?, result_path = ? WHERE run_id = ?",
                    (status, result_path, run_id)
                )
            else:
                conn.execute(
                    "UPDATE runs SET status = ? WHERE run_id = ?",
                    (status, run_id)
                )

    def record_cache_entry(self, cache_key: str, run_id: str) -> None:
        self._record_cache_entry(table="cache_entries", cache_key=cache_key, run_id=run_id)

    def record_temp_cache_entry(self, cache_key: str, run_id: str) -> None:
        self._record_cache_entry(table="temp_cache_entries", cache_key=cache_key, run_id=run_id)

    def _record_cache_entry(self, table: str, cache_key: str, run_id: str) -> None:
        created_at = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                f"""
                INSERT OR REPLACE INTO {table} (cache_key, run_id, status, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (cache_key, run_id, "succeeded", created_at)
            )

    def get_cached_run(self, cache_key: str) -> Optional[str]:
        return self._get_cached_run(table="cache_entries", cache_key=cache_key)

    def get_temp_cached_run(self, cache_key: str) -> Optional[str]:
        return self._get_cached_run(table="temp_cache_entries", cache_key=cache_key)

    def _get_cached_run(self, table: str, cache_key: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT run_id FROM {table} WHERE cache_key = ? AND status = ?",
                (cache_key, "succeeded")
            ).fetchone()
        if not row:
            return None
        return row["run_id"]

    def list_runs_for_cleanup(self, retention_days: int) -> List[Dict[str, Any]]:
        if retention_days <= 0:
            return []
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        candidates = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT run_id, status, created_at FROM runs"
            ).fetchall()
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

    def delete_run_records(self, run_id: str) -> List[str]:
        with self._connect() as conn:
            request_rows = conn.execute(
                "SELECT request_id FROM requests WHERE run_id = ?",
                (run_id,)
            ).fetchall()
            request_ids = [row["request_id"] for row in request_rows]
            if request_ids:
                placeholders = ",".join("?" for _ in request_ids)
                conn.execute(
                    f"DELETE FROM request_interactions WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                )
                conn.execute(
                    f"DELETE FROM request_interactive_runtime WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                )
                conn.execute(
                    f"DELETE FROM request_interaction_history WHERE request_id IN ({placeholders})",
                    tuple(request_ids),
                )
            conn.execute("DELETE FROM requests WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM cache_entries WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM temp_cache_entries WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
        return request_ids

    def list_request_ids(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT request_id FROM requests").fetchall()
        return [row["request_id"] for row in rows]

    def clear_all(self) -> Dict[str, int]:
        with self._connect() as conn:
            run_rows = conn.execute("SELECT run_id FROM runs").fetchall()
            request_rows = conn.execute("SELECT request_id FROM requests").fetchall()
            run_count = len(run_rows)
            request_count = len(request_rows)
            cache_rows = conn.execute("SELECT cache_key FROM cache_entries").fetchall()
            temp_cache_rows = conn.execute("SELECT cache_key FROM temp_cache_entries").fetchall()
            cache_count = len(cache_rows) + len(temp_cache_rows)
            conn.execute("DELETE FROM request_interactions")
            conn.execute("DELETE FROM request_interactive_runtime")
            conn.execute("DELETE FROM request_interaction_history")
            conn.execute("DELETE FROM cache_entries")
            conn.execute("DELETE FROM temp_cache_entries")
            conn.execute("DELETE FROM runs")
            conn.execute("DELETE FROM requests")
        return {"runs": run_count, "requests": request_count, "cache_entries": cache_count}

    def list_active_run_ids(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT run_id FROM runs WHERE status IN (?, ?, ?)",
                ("queued", "running", "waiting_user")
            ).fetchall()
        return [row["run_id"] for row in rows if row["run_id"]]

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def list_incomplete_runs(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
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
            ).fetchall()
        records: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            runtime_options_json = item.pop("runtime_options_json", "{}")
            session_handle_json = item.pop("session_handle_json", None)
            timeout_obj = item.get("effective_session_timeout_sec")
            try:
                item["runtime_options"] = json.loads(runtime_options_json or "{}")
            except Exception:
                item["runtime_options"] = {}
            if timeout_obj is None:
                item["interactive_session_config"] = None
            else:
                try:
                    item["interactive_session_config"] = {
                        "session_timeout_sec": int(timeout_obj)
                    }
                except Exception:
                    item["interactive_session_config"] = None
            try:
                item["session_handle"] = json.loads(session_handle_json) if session_handle_json else None
            except Exception:
                item["session_handle"] = None
            records.append(item)
        return records

    def set_recovery_info(
        self,
        run_id: str,
        *,
        recovery_state: str,
        recovery_reason: Optional[str] = None,
        recovered_at: Optional[str] = None,
    ) -> None:
        recovered_ts = recovered_at or datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET recovery_state = ?, recovered_at = ?, recovery_reason = ?
                WHERE run_id = ?
                """,
                (recovery_state, recovered_ts, recovery_reason, run_id),
            )

    def get_recovery_info(self, run_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT recovery_state, recovered_at, recovery_reason
                FROM runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
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

    def set_cancel_requested(self, run_id: str, requested: bool = True) -> bool:
        next_value = 1 if requested else 0
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cancel_requested FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if not row:
                return False
            current_value = int(row["cancel_requested"] or 0)
            conn.execute(
                "UPDATE runs SET cancel_requested = ? WHERE run_id = ?",
                (next_value, run_id),
            )
        return current_value != next_value

    def is_cancel_requested(self, run_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cancel_requested FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if not row:
            return False
        return int(row["cancel_requested"] or 0) == 1

    def _upsert_interactive_runtime(
        self,
        request_id: str,
        *,
        effective_session_timeout_sec: Optional[int] = None,
        session_handle_json: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT effective_session_timeout_sec, session_handle_json
                FROM request_interactive_runtime
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
            current = dict(row) if row else {}
            conn.execute(
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

    def set_interactive_profile(self, request_id: str, profile: Dict[str, Any]) -> None:
        timeout = profile.get("session_timeout_sec")
        if timeout is None:
            timeout = config.SYSTEM.SESSION_TIMEOUT_SEC
        self._upsert_interactive_runtime(request_id, effective_session_timeout_sec=int(timeout))

    def set_effective_session_timeout(self, request_id: str, timeout_sec: int) -> None:
        self._upsert_interactive_runtime(
            request_id,
            effective_session_timeout_sec=int(timeout_sec),
        )

    def get_interactive_profile(self, request_id: str) -> Optional[Dict[str, Any]]:
        timeout = self.get_effective_session_timeout(request_id)
        if timeout is None:
            return None
        return {"session_timeout_sec": int(timeout)}

    def get_effective_session_timeout(self, request_id: str) -> Optional[int]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT effective_session_timeout_sec
                FROM request_interactive_runtime
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
        if not row or row["effective_session_timeout_sec"] is None:
            return None
        return int(row["effective_session_timeout_sec"])

    def set_engine_session_handle(self, request_id: str, handle: Dict[str, Any]) -> None:
        self._upsert_interactive_runtime(
            request_id,
            session_handle_json=json.dumps(handle, sort_keys=True),
        )

    def get_engine_session_handle(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT session_handle_json
                FROM request_interactive_runtime
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
        if not row or row["session_handle_json"] is None:
            return None
        return json.loads(row["session_handle_json"])

    def clear_engine_session_handle(self, request_id: str) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE request_interactive_runtime
                SET session_handle_json = NULL, updated_at = ?
                WHERE request_id = ?
                """,
                (now, request_id),
            )

    def append_interaction_history(
        self,
        request_id: str,
        interaction_id: int,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
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
        with self._connect() as conn:
            conn.execute(
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

    def clear_pending_interaction(self, request_id: str) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE request_interactions
                SET state = 'consumed', updated_at = ?
                WHERE request_id = ? AND state = 'pending'
                """,
                (now, request_id),
            )

    def list_interaction_history(self, request_id: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT interaction_id, event_type, payload_json, created_at
                FROM request_interaction_history
                WHERE request_id = ?
                ORDER BY id ASC
                """,
                (request_id,),
            ).fetchall()
        history: List[Dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except Exception:
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

    def set_pending_interaction(self, request_id: str, payload: Dict[str, Any]) -> None:
        try:
            validate_pending_interaction(payload)
        except ProtocolSchemaViolation as exc:
            raise ValueError(
                f"{InteractiveErrorCode.PROTOCOL_SCHEMA_VIOLATION.value}: {exc}"
            ) from exc
        interaction_id = int(payload["interaction_id"])
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
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

    def get_pending_interaction(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload_json
                FROM request_interactions
                WHERE request_id = ? AND state = 'pending'
                ORDER BY interaction_id DESC
                LIMIT 1
                """,
                (request_id,),
            ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload_json"])
        except Exception:
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

    def get_interaction_count(self, request_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM request_interactions
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
        if not row:
            return 0
        return int(row["count"] or 0)

    def get_auto_decision_stats(self, request_id: str) -> Dict[str, Any]:
        history = self.list_interaction_history(request_id)
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

    def get_interaction_reply(
        self, request_id: str, interaction_id: int, idempotency_key: str
    ) -> Optional[Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT reply_json
                FROM request_interactions
                WHERE request_id = ? AND interaction_id = ? AND idempotency_key = ?
                """,
                (request_id, interaction_id, idempotency_key),
            ).fetchone()
        if not row or row["reply_json"] is None:
            return None
        return json.loads(row["reply_json"])

    def consume_interaction_reply(self, request_id: str, interaction_id: int) -> Optional[Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT state, reply_json
                FROM request_interactions
                WHERE request_id = ? AND interaction_id = ?
                """,
                (request_id, interaction_id),
            ).fetchone()
            if not row or row["state"] != "answered" or row["reply_json"] is None:
                return None
            conn.execute(
                """
                UPDATE request_interactions
                SET state = ?, updated_at = ?
                WHERE request_id = ? AND interaction_id = ?
                """,
                ("consumed", datetime.utcnow().isoformat(), request_id, interaction_id),
            )
            return json.loads(row["reply_json"])

    def submit_interaction_reply(
        self,
        request_id: str,
        interaction_id: int,
        response: Any,
        idempotency_key: Optional[str],
    ) -> str:
        """
        Returns one of: accepted | idempotent | stale | idempotency_conflict.
        """
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT state, idempotency_key, reply_json
                FROM request_interactions
                WHERE request_id = ? AND interaction_id = ?
                """,
                (request_id, interaction_id),
            ).fetchone()
            if not row:
                return "stale"

            state = row["state"]
            existing_key = row["idempotency_key"]
            existing_reply = (
                json.loads(row["reply_json"])
                if row["reply_json"] is not None
                else None
            )
            if state != "pending":
                if idempotency_key and existing_key == idempotency_key:
                    if existing_reply == response:
                        return "idempotent"
                    return "idempotency_conflict"
                return "stale"

            now = datetime.utcnow().isoformat()
            conn.execute(
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
            return "accepted"


run_store = RunStore()
logger = logging.getLogger(__name__)
