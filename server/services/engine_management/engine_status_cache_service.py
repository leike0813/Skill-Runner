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
from server.services.platform import aiosqlite_compat as aiosqlite
from server.services.platform.sqlite_db_handle import sqlite_db_handle_registry

logger = logging.getLogger(__name__)

_LEGACY_PARSE_EXCEPTIONS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    TypeError,
    ValueError,
)
_SQLITE_EXCEPTIONS = (sqlite3.DatabaseError, OSError, RuntimeError, ValueError, TypeError)
_ENGINE_STATUS_IO_EXCEPTIONS = (asyncio.TimeoutError,) + _SQLITE_EXCEPTIONS
_DB_OPERATION_TIMEOUT_SEC = 2.0


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
        self._db_path = (db_path or Path(config.SYSTEM.ENGINE_STATUS_DB)).resolve()
        self._legacy_cache_path = self._manager.profile.data_dir / "agent_status.json"
        self._write_lock = asyncio.Lock()
        self._scheduler: AsyncIOScheduler | None = None
        self._table_lock = threading.Lock()
        self._table_ready = False
        self._snapshot_lock = threading.Lock()
        self._snapshot_payload: Dict[str, Dict[str, object]] = {}

    @property
    def db_path(self) -> Path:
        return self._db_path

    def get_snapshot(self) -> Dict[str, EngineVersionStatus]:
        payload = self._read_snapshot_payload()
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
        current = self._read_snapshot_payload()
        status = self._manager.collect_engine_status(engine)
        current[engine] = {"present": status.present, "version": status.version}
        await self.write_payload(current)
        return EngineVersionStatus(present=status.present, version=status.version or None)

    async def write_payload(self, payload: Dict[str, Dict[str, object]]) -> None:
        normalized = self._normalize_payload(payload)
        self._replace_snapshot_payload(normalized)
        await self._persist_payload_best_effort(normalized, action="write_payload_db")

    async def load_persisted(self) -> Dict[str, EngineVersionStatus]:
        payload = await self._read_payload_best_effort()
        self._replace_snapshot_payload(payload)
        return self.get_snapshot()

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
        await self.write_payload(format_status_payload(status))

    def _read_snapshot_payload(self) -> Dict[str, Dict[str, object]]:
        with self._snapshot_lock:
            return {engine: dict(item) for engine, item in self._snapshot_payload.items()}

    def _replace_snapshot_payload(self, payload: Dict[str, Dict[str, object]]) -> None:
        normalized = self._normalize_payload(payload)
        with self._snapshot_lock:
            self._snapshot_payload = {engine: dict(item) for engine, item in normalized.items()}

    def _ensure_table(self) -> None:
        raise RuntimeError("EngineStatusCacheService._ensure_table is async-only")

    async def _ensure_table_async(self, conn: aiosqlite.Connection) -> None:
        if self._table_ready:
            return
        async with asyncio.Lock():
            if self._table_ready:
                return
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS engine_status_cache (
                    engine TEXT PRIMARY KEY,
                    present INTEGER NOT NULL,
                    version TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await conn.commit()
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

    async def _persist_payload_best_effort(
        self,
        payload: Dict[str, Dict[str, object]],
        *,
        action: str,
    ) -> None:
        if not payload:
            return
        async with self._write_lock:
            try:
                await asyncio.wait_for(
                    self._write_payload_async(payload),
                    timeout=_DB_OPERATION_TIMEOUT_SEC,
                )
            except _ENGINE_STATUS_IO_EXCEPTIONS as exc:
                logger.warning(
                    "engine status cache persistence failed; keeping in-memory snapshot",
                    extra={
                        "component": "engine_management.engine_status_cache_service",
                        "action": action,
                        "error_type": type(exc).__name__,
                        "fallback": "memory_snapshot",
                    },
                    exc_info=True,
                )

    async def _read_payload_best_effort(self) -> Dict[str, Dict[str, object]]:
        try:
            return await asyncio.wait_for(
                self._read_payload_async(),
                timeout=_DB_OPERATION_TIMEOUT_SEC,
            )
        except _ENGINE_STATUS_IO_EXCEPTIONS as exc:
            logger.warning(
                "engine status cache unreadable; keeping in-memory snapshot",
                extra={
                    "component": "engine_management.engine_status_cache_service",
                    "action": "read_payload_db",
                    "error_type": type(exc).__name__,
                    "fallback": "memory_snapshot",
                },
                exc_info=True,
            )
            return self._read_snapshot_payload()

    async def _write_payload_async(self, payload: Dict[str, Dict[str, object]]) -> None:
        normalized = self._normalize_payload(payload)
        if not normalized:
            return
        async with sqlite_db_handle_registry.operation(self._db_path) as conn:
            await self._ensure_table_async(conn)
            updated_at = _utc_now_iso()
            await conn.executemany(
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
            await conn.commit()

    async def _read_payload_async(self) -> Dict[str, Dict[str, object]]:
        try:
            async with sqlite_db_handle_registry.operation(self._db_path) as conn:
                await self._ensure_table_async(conn)
                await self._migrate_legacy_cache_if_needed(conn)
                cur = await conn.execute("SELECT engine, present, version FROM engine_status_cache")
                rows = await cur.fetchall()
        except _SQLITE_EXCEPTIONS as exc:
            logger.warning(
                "engine status cache unreadable; falling back to empty snapshot",
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

    async def _migrate_legacy_cache_if_needed(self, conn: aiosqlite.Connection) -> None:
        legacy = self._read_legacy_payload()
        if not legacy:
            return
        cur = await conn.execute("SELECT COUNT(*) FROM engine_status_cache")
        row = await cur.fetchone()
        existing_count = int(row[0]) if row else 0
        if existing_count > 0:
            return
        updated_at = _utc_now_iso()
        await conn.executemany(
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
        await conn.commit()
        logger.info(
            "Migrated legacy agent_status.json into engine status cache table",
            extra={
                "component": "engine_management.engine_status_cache_service",
                "action": "migrate_legacy_cache",
                "legacy_path": str(self._legacy_cache_path),
                "db_path": str(self._db_path),
            },
        )


engine_status_cache_service = EngineStatusCacheService()
