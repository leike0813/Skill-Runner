from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import threading
from typing import TypeVar

from server.services.platform import aiosqlite_compat as aiosqlite


T = TypeVar("T")
logger = logging.getLogger(__name__)
SQLITE_HANDLE_CLOSE_TIMEOUT_SECONDS = 1.0


class SQLiteDbHandle:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path.resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: aiosqlite.Connection | None = None
        self._owner_loop: asyncio.AbstractEventLoop | None = None
        self._open_lock = asyncio.Lock()
        self._operation_lock = asyncio.Lock()

    @property
    def is_open(self) -> bool:
        return self._connection is not None

    async def _ensure_open(self) -> aiosqlite.Connection:
        if self._connection is not None:
            return self._connection
        async with self._open_lock:
            if self._connection is not None:
                return self._connection
            conn = await aiosqlite.connect(str(self.db_path))
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA busy_timeout = 5000")
            await conn.execute("PRAGMA foreign_keys = ON")
            await conn.commit()
            self._connection = conn
            self._owner_loop = asyncio.get_running_loop()
            return conn

    @asynccontextmanager
    async def operation(self) -> AsyncIterator[aiosqlite.Connection]:
        conn = await self._ensure_open()
        async with self._operation_lock:
            yield conn

    async def close(self) -> None:
        owner_loop = self._owner_loop
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        if owner_loop is not None and owner_loop is not current_loop and owner_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._close_on_owner_loop(), owner_loop)
            try:
                await asyncio.wait_for(
                    asyncio.wrap_future(future),
                    timeout=SQLITE_HANDLE_CLOSE_TIMEOUT_SECONDS,
                )
            except (asyncio.TimeoutError, RuntimeError, OSError, ValueError):
                logger.warning(
                    "SQLite connection close did not finish on owner loop",
                    extra={
                        "component": "platform.sqlite_db_handle",
                        "db_path": str(self.db_path),
                    },
                    exc_info=True,
                )
            return
        await self._close_on_owner_loop()

    async def _close_on_owner_loop(self) -> None:
        async with self._operation_lock:
            conn = self._connection
            self._connection = None
            self._owner_loop = None
            if conn is not None:
                try:
                    await asyncio.wait_for(conn.close(), timeout=SQLITE_HANDLE_CLOSE_TIMEOUT_SECONDS)
                except (asyncio.TimeoutError, RuntimeError, OSError, ValueError):
                    logger.warning(
                        "SQLite connection close did not finish cleanly",
                        extra={
                            "component": "platform.sqlite_db_handle",
                            "db_path": str(self.db_path),
                        },
                        exc_info=True,
                    )


class SQLiteDbHandleRegistry:
    def __init__(self) -> None:
        self._handles: dict[Path, SQLiteDbHandle] = {}
        self._lock = threading.Lock()

    def get(self, db_path: Path | str) -> SQLiteDbHandle:
        resolved = Path(db_path).resolve()
        with self._lock:
            handle = self._handles.get(resolved)
            if handle is None:
                handle = SQLiteDbHandle(resolved)
                self._handles[resolved] = handle
            return handle

    @asynccontextmanager
    async def operation(self, db_path: Path | str) -> AsyncIterator[aiosqlite.Connection]:
        async with self.get(db_path).operation() as conn:
            yield conn

    async def close_all(self) -> None:
        with self._lock:
            handles = list(self._handles.values())
            self._handles.clear()
        for handle in handles:
            await handle.close()

    async def close_path(self, db_path: Path | str) -> None:
        resolved = Path(db_path).resolve()
        with self._lock:
            handle = self._handles.pop(resolved, None)
        if handle is not None:
            await handle.close()


sqlite_db_handle_registry = SQLiteDbHandleRegistry()


class SQLiteSyncBridge:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is not None and self._thread is not None and self._thread.is_alive():
                return self._loop
            ready = threading.Event()
            loop_holder: dict[str, asyncio.AbstractEventLoop] = {}

            def _run() -> None:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop_holder["loop"] = loop
                ready.set()
                loop.run_forever()

            thread = threading.Thread(target=_run, name="skill-runner-sqlite-sync", daemon=True)
            thread.start()
            ready.wait()
            self._loop = loop_holder["loop"]
            self._thread = thread
            return self._loop

    def run(self, func: Callable[[aiosqlite.Connection], Awaitable[T]], *, db_path: Path | str) -> T:
        async def _operation() -> T:
            async with sqlite_db_handle_registry.operation(db_path) as conn:
                return await func(conn)

        loop = self._ensure_loop()
        return asyncio.run_coroutine_threadsafe(_operation(), loop).result()

    async def close(self) -> None:
        loop = self._loop
        if loop is None:
            return
        loop.call_soon_threadsafe(loop.stop)
        self._loop = None
        self._thread = None


sqlite_sync_bridge = SQLiteSyncBridge()
