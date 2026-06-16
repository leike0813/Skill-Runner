from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar


Row = sqlite3.Row
SQLITE_BUSY_TIMEOUT_MS = 5000
SQLITE_BUSY_TIMEOUT_SECONDS = SQLITE_BUSY_TIMEOUT_MS / 1000
SQLITE_BUSY_RETRY_DELAYS = (0.025, 0.075, 0.150)

T = TypeVar("T")


def _is_locked_operational_error(exc: sqlite3.OperationalError) -> bool:
    sqlite_error_name = getattr(exc, "sqlite_errorname", "")
    if sqlite_error_name in {"SQLITE_BUSY", "SQLITE_LOCKED"}:
        return True
    message = str(exc).lower()
    return "database is locked" in message or "database table is locked" in message


class Cursor:
    def __init__(self, cursor: sqlite3.Cursor, connection: "Connection") -> None:
        self._cursor = cursor
        self._connection = connection

    @property
    def rowcount(self) -> int:
        return int(self._cursor.rowcount)

    async def fetchone(self):
        return await self._connection._run_with_connection_lock(self._cursor.fetchone)

    async def fetchall(self):
        return await self._connection._run_with_connection_lock(self._cursor.fetchall)

    async def close(self) -> None:
        await self._connection._run_with_connection_lock(self._cursor.close)


class Connection:
    def __init__(self, db_path: str, *, semaphore: asyncio.Semaphore | None = None) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._row_factory = sqlite3.Row
        self._lock = asyncio.Lock()
        self._semaphore = semaphore
        self._semaphore_acquired = False
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="skill-runner-sqlite")

    @property
    def row_factory(self):
        if self._conn is not None:
            return self._conn.row_factory
        return self._row_factory

    @row_factory.setter
    def row_factory(self, value) -> None:
        self._row_factory = value
        if self._conn is not None:
            self._conn.row_factory = value

    async def execute(self, sql: str, parameters: Iterable[Any] = ()):
        params = tuple(parameters)

        def _execute() -> sqlite3.Cursor:
            conn = self._require_open_connection()
            return conn.execute(sql, params)

        cursor = await self._run_with_connection_lock(_execute)
        return Cursor(cursor, self)

    async def executemany(self, sql: str, seq_of_parameters: Iterable[Iterable[Any]]):
        normalized = [tuple(params) for params in seq_of_parameters]

        def _executemany() -> sqlite3.Cursor:
            conn = self._require_open_connection()
            return conn.executemany(sql, normalized)

        await self._run_with_connection_lock(_executemany)

    async def commit(self) -> None:
        await self._run_with_connection_lock(lambda: self._require_open_connection().commit())

    async def rollback(self) -> None:
        await self._run_with_connection_lock(lambda: self._require_open_connection().rollback())

    async def close(self) -> None:
        async with self._lock:
            conn = self._conn
            self._conn = None
            try:
                if conn is not None:
                    await self._run_with_retry(conn.close)
            finally:
                if self._semaphore is not None and self._semaphore_acquired:
                    self._semaphore.release()
                    self._semaphore_acquired = False
                self._executor.shutdown(wait=False, cancel_futures=False)

    async def __aenter__(self) -> "Connection":
        await self._ensure_open()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    def _require_open_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SQLite connection is not open")
        return self._conn

    async def _ensure_open(self) -> None:
        if self._conn is not None:
            return
        async with self._lock:
            if self._conn is not None:
                return
            if self._semaphore is not None and not self._semaphore_acquired:
                await self._semaphore.acquire()
                self._semaphore_acquired = True
            try:
                self._conn = await self._run_with_retry(self._open_connection)
            except Exception:
                if self._semaphore is not None and self._semaphore_acquired:
                    self._semaphore.release()
                    self._semaphore_acquired = False
                raise

    def _open_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self._db_path,
            timeout=SQLITE_BUSY_TIMEOUT_SECONDS,
            check_same_thread=False,
        )
        conn.row_factory = self._row_factory
        conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    async def _run_with_connection_lock(self, operation: Callable[[], T]) -> T:
        await self._ensure_open()
        async with self._lock:
            return await self._run_with_retry(operation)

    async def _run_with_retry(self, operation: Callable[[], T]) -> T:
        attempt = 0
        while True:
            try:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(self._executor, operation)
            except sqlite3.OperationalError as exc:
                if attempt >= len(SQLITE_BUSY_RETRY_DELAYS) or not _is_locked_operational_error(exc):
                    raise
                await asyncio.sleep(SQLITE_BUSY_RETRY_DELAYS[attempt])
                attempt += 1


def connect(db_path: str, *, semaphore: asyncio.Semaphore | None = None) -> Connection:
    return Connection(db_path, semaphore=semaphore)
