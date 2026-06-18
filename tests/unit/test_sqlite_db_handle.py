from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from server.services.orchestration.run_store_database import RunStoreDatabase
from server.services.platform.sqlite_db_handle import SQLiteDbHandleRegistry, sqlite_db_handle_registry


def test_sqlite_db_handle_registry_reuses_handle_for_same_resolved_path(tmp_path: Path):
    registry = SQLiteDbHandleRegistry()
    db_path = tmp_path / "store.db"

    first = registry.get(db_path)
    second = registry.get(tmp_path / "." / "store.db")

    assert first is second
    assert registry.get(tmp_path / "other.db") is not first


@pytest.mark.asyncio
async def test_sqlite_db_handle_serializes_operations_for_same_db(tmp_path: Path):
    registry = SQLiteDbHandleRegistry()
    db_path = tmp_path / "store.db"
    order: list[str] = []

    async def first_operation() -> None:
        async with registry.operation(db_path):
            order.append("first-start")
            await asyncio.sleep(0.02)
            order.append("first-end")

    async def second_operation() -> None:
        await asyncio.sleep(0)
        async with registry.operation(db_path):
            order.append("second")

    await asyncio.gather(first_operation(), second_operation())
    await registry.close_all()

    assert order == ["first-start", "first-end", "second"]


@pytest.mark.asyncio
async def test_sqlite_db_handle_allows_different_db_operations_to_progress(tmp_path: Path):
    registry = SQLiteDbHandleRegistry()
    first_entered = asyncio.Event()
    second_entered = asyncio.Event()

    async def first_operation() -> None:
        async with registry.operation(tmp_path / "a.db"):
            first_entered.set()
            await second_entered.wait()

    async def second_operation() -> None:
        await first_entered.wait()
        async with registry.operation(tmp_path / "b.db"):
            second_entered.set()

    await asyncio.wait_for(asyncio.gather(first_operation(), second_operation()), timeout=1)
    await registry.close_all()


@pytest.mark.asyncio
async def test_run_store_database_connect_reuses_shared_connection(tmp_path: Path):
    database = RunStoreDatabase(tmp_path / "runs.db")

    async with database.connect() as first:
        first_id = id(first)
    async with database.connect() as second:
        second_id = id(second)

    await sqlite_db_handle_registry.close_path(database.db_path)

    assert second_id == first_id
