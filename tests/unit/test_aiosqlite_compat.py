from __future__ import annotations

import inspect
from pathlib import Path
import sqlite3

import pytest

from server.services.platform import aiosqlite_compat as aiosqlite


@pytest.mark.asyncio
async def test_aiosqlite_compat_crud_preserves_row_factory(tmp_path):
    async with aiosqlite.connect(str(tmp_path / "compat.db")) as conn:
        await conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        await conn.execute("INSERT INTO items (name) VALUES (?)", ("alpha",))
        await conn.commit()

        cursor = await conn.execute("SELECT id, name FROM items")
        row = await cursor.fetchone()

    assert isinstance(row, sqlite3.Row)
    assert row["name"] == "alpha"


@pytest.mark.asyncio
async def test_aiosqlite_compat_shutdown_executor_is_noop():
    await aiosqlite.shutdown_executor()


def test_aiosqlite_compat_is_thin_official_aiosqlite_shim():
    source = inspect.getsource(aiosqlite)

    assert "ThreadPoolExecutor" not in source
    assert "_run_with_retry" not in source
    assert "SQLITE_BUSY_RETRY_DELAYS" not in source


@pytest.mark.asyncio
async def test_aiosqlite_connect_ignores_legacy_semaphore_argument(tmp_path):
    async with aiosqlite.connect(str(tmp_path / "threaded.db"), semaphore=object()) as conn:
        await conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY)")
        await conn.commit()


def test_runtime_service_code_does_not_directly_open_sqlite_connections():
    root = Path(__file__).resolve().parents[2]
    searched_roots = (
        root / "server" / "services",
        root / "server" / "runtime",
        root / "server" / "routers",
    )
    allowed = {
        root / "server" / "services" / "platform" / "aiosqlite_compat.py",
    }
    offenders: list[str] = []
    for searched_root in searched_roots:
        for path in searched_root.rglob("*.py"):
            if path in allowed:
                continue
            text = path.read_text(encoding="utf-8")
            if "sqlite3.connect" in text:
                offenders.append(str(path.relative_to(root)))

    assert offenders == []
