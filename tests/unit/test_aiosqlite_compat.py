from __future__ import annotations

import sqlite3
import threading

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
async def test_aiosqlite_connect_runs_off_event_loop_thread(tmp_path, monkeypatch):
    event_loop_thread_id = threading.get_ident()
    connect_thread_ids: list[int] = []
    real_connect = sqlite3.connect

    def _recording_connect(*args, **kwargs):
        connect_thread_ids.append(threading.get_ident())
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(aiosqlite.sqlite3, "connect", _recording_connect)

    async with aiosqlite.connect(str(tmp_path / "threaded.db")) as conn:
        await conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY)")
        await conn.commit()

    assert connect_thread_ids
    assert all(thread_id != event_loop_thread_id for thread_id in connect_thread_ids)


@pytest.mark.asyncio
async def test_aiosqlite_operations_run_off_event_loop_thread(monkeypatch):
    event_loop_thread_id = threading.get_ident()
    operation_thread_ids: list[int] = []

    class _FakeCursor:
        rowcount = 1

        def fetchone(self):
            operation_thread_ids.append(threading.get_ident())
            return ("ok",)

        def fetchall(self):
            operation_thread_ids.append(threading.get_ident())
            return []

        def close(self):
            operation_thread_ids.append(threading.get_ident())

    class _FakeConnection:
        row_factory = None

        def execute(self, sql, parameters=()):
            _ = sql
            _ = parameters
            operation_thread_ids.append(threading.get_ident())
            return _FakeCursor()

        def commit(self):
            operation_thread_ids.append(threading.get_ident())

        def close(self):
            operation_thread_ids.append(threading.get_ident())

    monkeypatch.setattr(aiosqlite.sqlite3, "connect", lambda *args, **kwargs: _FakeConnection())

    async with aiosqlite.connect(":memory:") as conn:
        cursor = await conn.execute("SELECT 1")
        assert await cursor.fetchone() == ("ok",)
        await cursor.close()
        await conn.commit()

    assert operation_thread_ids
    assert all(thread_id != event_loop_thread_id for thread_id in operation_thread_ids)
    assert len(set(operation_thread_ids)) == 1


@pytest.mark.asyncio
async def test_aiosqlite_retries_transient_locked_error(monkeypatch):
    monkeypatch.setattr(aiosqlite, "SQLITE_BUSY_RETRY_DELAYS", (0, 0, 0))

    class _FakeCursor:
        rowcount = 1

        def fetchone(self):
            return ("ok",)

        def fetchall(self):
            return []

        def close(self):
            return None

    class _FakeConnection:
        row_factory = None

        def __init__(self) -> None:
            self.select_calls = 0

        def execute(self, sql, parameters=()):
            _ = parameters
            if sql == "SELECT 1":
                self.select_calls += 1
                if self.select_calls < 3:
                    raise sqlite3.OperationalError("database is locked")
            return _FakeCursor()

        def close(self):
            return None

    fake_conn = _FakeConnection()
    monkeypatch.setattr(aiosqlite.sqlite3, "connect", lambda *args, **kwargs: fake_conn)

    async with aiosqlite.connect(":memory:") as conn:
        cursor = await conn.execute("SELECT 1")
        row = await cursor.fetchone()

    assert row == ("ok",)
    assert fake_conn.select_calls == 3


@pytest.mark.asyncio
async def test_aiosqlite_raises_after_locked_retry_budget(monkeypatch):
    monkeypatch.setattr(aiosqlite, "SQLITE_BUSY_RETRY_DELAYS", (0, 0, 0))

    class _FakeCursor:
        rowcount = 0

    class _FakeConnection:
        row_factory = None

        def __init__(self) -> None:
            self.select_calls = 0

        def execute(self, sql, parameters=()):
            _ = parameters
            if sql == "SELECT 1":
                self.select_calls += 1
                raise sqlite3.OperationalError("database table is locked")
            return _FakeCursor()

        def close(self):
            return None

    fake_conn = _FakeConnection()
    monkeypatch.setattr(aiosqlite.sqlite3, "connect", lambda *args, **kwargs: fake_conn)

    async with aiosqlite.connect(":memory:") as conn:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            await conn.execute("SELECT 1")

    assert fake_conn.select_calls == 4
