import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.config import config
from server.models import SkillInstallStatus


class SkillInstallStore:
    """SQLite-backed store for skill package install request lifecycle."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or Path(config.SYSTEM.SKILL_INSTALLS_DB)
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

    def create_install(self, request_id: str) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO skill_installs (
                    request_id, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?)
                """,
                (request_id, SkillInstallStatus.QUEUED.value, now, now)
            )

    def update_running(self, request_id: str) -> None:
        self._update(
            request_id,
            status=SkillInstallStatus.RUNNING.value,
            error=None
        )

    def update_succeeded(
        self,
        request_id: str,
        skill_id: str,
        version: str,
        action: str
    ) -> None:
        self._update(
            request_id,
            status=SkillInstallStatus.SUCCEEDED.value,
            skill_id=skill_id,
            version=version,
            action=action,
            error=None
        )

    def update_failed(self, request_id: str, error: str) -> None:
        self._update(
            request_id,
            status=SkillInstallStatus.FAILED.value,
            error=error
        )

    def _update(self, request_id: str, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = datetime.utcnow().isoformat()
        columns = ", ".join(f"{key} = ?" for key in fields.keys())
        values = list(fields.values()) + [request_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE skill_installs SET {columns} WHERE request_id = ?",
                values
            )

    def get_install(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM skill_installs WHERE request_id = ?",
                (request_id,)
            ).fetchone()
        if not row:
            return None
        return dict(row)

    def list_installs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM skill_installs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()
        return [dict(row) for row in rows]


skill_install_store = SkillInstallStore()
