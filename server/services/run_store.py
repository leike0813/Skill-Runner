import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta

from ..config import config


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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    cache_key TEXT,
                    status TEXT,
                    result_path TEXT,
                    artifacts_manifest_path TEXT,
                    created_at TEXT NOT NULL
                )
                """
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

    def create_request(
        self,
        request_id: str,
        skill_id: str,
        engine: str,
        parameter: Dict[str, Any],
        engine_options: Dict[str, Any],
        runtime_options: Dict[str, Any]
    ) -> None:
        created_at = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO requests (
                    request_id, skill_id, engine, parameter_json,
                    engine_options_json, runtime_options_json, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    skill_id,
                    engine,
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
        data["parameter"] = json.loads(data["parameter_json"])
        data["engine_options"] = json.loads(data["engine_options_json"])
        data["runtime_options"] = json.loads(data["runtime_options_json"])
        return data

    def create_run(self, run_id: str, cache_key: str, status: str, result_path: str = "", artifacts_manifest_path: str = "") -> None:
        created_at = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, cache_key, status, result_path, artifacts_manifest_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, cache_key, status, result_path, artifacts_manifest_path, created_at)
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
        created_at = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache_entries (cache_key, run_id, status, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (cache_key, run_id, "succeeded", created_at)
            )

    def get_cached_run(self, cache_key: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT run_id FROM cache_entries WHERE cache_key = ? AND status = ?",
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
            if status in ("running", "queued"):
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
            conn.execute("DELETE FROM requests WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM cache_entries WHERE run_id = ?", (run_id,))
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
            cache_count = len(cache_rows)
            conn.execute("DELETE FROM cache_entries")
            conn.execute("DELETE FROM runs")
            conn.execute("DELETE FROM requests")
        return {"runs": run_count, "requests": request_count, "cache_entries": cache_count}


run_store = RunStore()
