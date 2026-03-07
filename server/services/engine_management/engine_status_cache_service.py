import asyncio
import json
import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from server.config import config
from server.config_registry import keys
from server.services.engine_management.agent_cli_manager import (
    AgentCliManager,
    EngineStatus,
    format_status_payload,
)

logger = logging.getLogger(__name__)

_LEGACY_PARSE_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    TypeError,
    ValueError,
)
_SQLITE_EXCEPTIONS = (sqlite3.DatabaseError, OSError, RuntimeError, ValueError, TypeError)


def _supported_engines() -> tuple[str, ...]:
    return tuple(keys.ENGINE_KEYS)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EngineVersionStatus:
    present: bool
    version: str | None


class EngineStatusCacheService:
    def __init__(
        self,
        manager: AgentCliManager | None = None,
        *,
        db_path: Path | None = None,
    ) -> None:
        self._manager = manager or AgentCliManager()
        self._db_path = (db_path or Path(config.SYSTEM.RUNS_DB)).resolve()
        self._legacy_cache_path = self._manager.profile.data_dir / "agent_status.json"
        self._write_lock = asyncio.Lock()
        self._scheduler: AsyncIOScheduler | None = None
        self._table_lock = threading.Lock()
        self._table_ready = False

    @property
    def db_path(self) -> Path:
        return self._db_path

    def get_snapshot(self) -> Dict[str, EngineVersionStatus]:
        payload = self._read_payload()
        snapshot: Dict[str, EngineVersionStatus] = {}
        for engine in _supported_engines():
            raw = payload.get(engine, {})
            if not isinstance(raw, dict):
                raw = {}
            present = bool(raw.get("present", False))
            version = raw.get("version")
            snapshot[engine] = EngineVersionStatus(
                present=present,
                version=version if isinstance(version, str) and version.strip() else None,
            )
        return snapshot

    def get_engine_status(self, engine: str) -> EngineVersionStatus:
        return self.get_snapshot().get(engine, EngineVersionStatus(present=False, version=None))

    def get_engine_version(self, engine: str) -> str | None:
        return self.get_engine_status(engine).version

    async def refresh_all(self) -> Dict[str, EngineVersionStatus]:
        status = self._manager.collect_status()
        await self._write_status(status)
        return {
            engine: EngineVersionStatus(present=item.present, version=item.version or None)
            for engine, item in status.items()
        }

    async def refresh_engine(self, engine: str) -> EngineVersionStatus:
        current = self._read_payload()
        status = self._manager.collect_engine_status(engine)
        current[engine] = {"present": status.present, "version": status.version}
        await self.write_payload(current)
        return EngineVersionStatus(present=status.present, version=status.version or None)

    async def write_payload(self, payload: Dict[str, Dict[str, object]]) -> None:
        await self._write_payload(payload)

    def start(self) -> None:
        if self._scheduler is not None and self._scheduler.running:
            return
        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self.refresh_all,
            "interval",
            days=1,
            id="engine_status_cache_daily_refresh",
            replace_existing=True,
        )
        self._scheduler.start()

    def stop(self) -> None:
        if self._scheduler is None:
            return
        try:
            self._scheduler.shutdown(wait=False)
        finally:
            self._scheduler = None

    async def _write_status(self, status: Dict[str, EngineStatus]) -> None:
        await self._write_payload(format_status_payload(status))

    def _ensure_table(self) -> None:
        if self._table_ready:
            return
        with self._table_lock:
            if self._table_ready:
                return
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS engine_status_cache (
                        engine TEXT PRIMARY KEY,
                        present INTEGER NOT NULL,
                        version TEXT,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.commit()
            self._table_ready = True

    def _normalize_payload(self, payload: Dict[str, Dict[str, object]]) -> Dict[str, Dict[str, object]]:
        supported = set(_supported_engines())
        normalized: Dict[str, Dict[str, object]] = {}
        for engine, item in payload.items():
            if engine not in supported or not isinstance(item, dict):
                continue
            normalized[engine] = {
                "present": bool(item.get("present", False)),
                "version": str(item.get("version") or ""),
            }
        return normalized

    async def _write_payload(self, payload: Dict[str, Dict[str, object]]) -> None:
        normalized = self._normalize_payload(payload)
        if not normalized:
            return
        async with self._write_lock:
            self._ensure_table()
            updated_at = _utc_now_iso()
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.executemany(
                    """
                    INSERT INTO engine_status_cache (engine, present, version, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(engine) DO UPDATE SET
                        present=excluded.present,
                        version=excluded.version,
                        updated_at=excluded.updated_at
                    """,
                    [
                        (
                            engine,
                            1 if bool(item.get("present")) else 0,
                            str(item.get("version") or ""),
                            updated_at,
                        )
                        for engine, item in normalized.items()
                    ],
                )
                conn.commit()

    def _read_payload(self) -> Dict[str, Dict[str, object]]:
        try:
            self._ensure_table()
            self._migrate_legacy_cache_if_needed()
            with sqlite3.connect(str(self._db_path)) as conn:
                cur = conn.execute("SELECT engine, present, version FROM engine_status_cache")
                rows = cur.fetchall()
        except _SQLITE_EXCEPTIONS as exc:
            logger.warning(
                "engine status cache unreadable from runs.db; falling back to empty snapshot",
                extra={
                    "component": "engine_management.engine_status_cache_service",
                    "action": "read_payload_db",
                    "error_type": type(exc).__name__,
                    "fallback": "empty_snapshot",
                },
                exc_info=True,
            )
            return {}

        payload: Dict[str, Dict[str, object]] = {}
        for engine, present, version in rows:
            if not isinstance(engine, str):
                continue
            if engine not in set(_supported_engines()):
                continue
            payload[engine] = {
                "present": bool(present),
                "version": str(version or ""),
            }
        return payload

    def _read_legacy_payload(self) -> Dict[str, Dict[str, object]]:
        if not self._legacy_cache_path.exists():
            return {}
        try:
            raw = json.loads(self._legacy_cache_path.read_text(encoding="utf-8"))
        except _LEGACY_PARSE_EXCEPTIONS as exc:
            logger.warning(
                "legacy engine status cache unreadable; ignoring legacy file",
                extra={
                    "component": "engine_management.engine_status_cache_service",
                    "action": "read_payload_legacy",
                    "error_type": type(exc).__name__,
                    "fallback": "ignore_legacy_file",
                },
                exc_info=True,
            )
            return {}
        if not isinstance(raw, dict):
            return {}
        normalized = self._normalize_payload(raw)
        return normalized

    def _migrate_legacy_cache_if_needed(self) -> None:
        legacy = self._read_legacy_payload()
        if not legacy:
            return
        with sqlite3.connect(str(self._db_path)) as conn:
            cur = conn.execute("SELECT COUNT(*) FROM engine_status_cache")
            row = cur.fetchone()
            existing_count = int(row[0]) if row else 0
            if existing_count > 0:
                return
            updated_at = _utc_now_iso()
            conn.executemany(
                """
                INSERT INTO engine_status_cache (engine, present, version, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(engine) DO UPDATE SET
                    present=excluded.present,
                    version=excluded.version,
                    updated_at=excluded.updated_at
                """,
                [
                    (
                        engine,
                        1 if bool(item.get("present")) else 0,
                        str(item.get("version") or ""),
                        updated_at,
                    )
                    for engine, item in legacy.items()
                ],
            )
            conn.commit()
        logger.info(
            "Migrated legacy agent_status.json into runs.db engine_status_cache table",
            extra={
                "component": "engine_management.engine_status_cache_service",
                "action": "migrate_legacy_cache",
                "legacy_path": str(self._legacy_cache_path),
                "db_path": str(self._db_path),
            },
        )


engine_status_cache_service = EngineStatusCacheService()
