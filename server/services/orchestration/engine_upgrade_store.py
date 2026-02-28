import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from server.config import config
from server.models import EngineUpgradeTaskStatus


class EngineUpgradeStore:
    """SQLite-backed store for engine upgrade task lifecycle."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path(config.SYSTEM.ENGINE_UPGRADES_DB)
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

    def create_task(self, request_id: str, mode: str, requested_engine: Optional[str]) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
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

    def update_task(
        self,
        request_id: str,
        *,
        status: Optional[EngineUpgradeTaskStatus] = None,
        results: Optional[Dict[str, Any]] = None,
    ) -> None:
        updates: Dict[str, Any] = {"updated_at": datetime.utcnow().isoformat()}
        if status is not None:
            updates["status"] = status.value
        if results is not None:
            updates["results_json"] = json.dumps(results, sort_keys=True)
        columns = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [request_id]
        with self._connect() as conn:
            conn.execute(f"UPDATE engine_upgrades SET {columns} WHERE request_id = ?", values)

    def get_task(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM engine_upgrades WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["results"] = json.loads(payload.pop("results_json"))
        return payload

    def has_running_task(self) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT request_id FROM engine_upgrades WHERE status = ? LIMIT 1",
                (EngineUpgradeTaskStatus.RUNNING.value,),
            ).fetchone()
        return row is not None


engine_upgrade_store = EngineUpgradeStore()
