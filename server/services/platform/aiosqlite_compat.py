from __future__ import annotations

import sqlite3
from typing import Any, Iterable


Row = sqlite3.Row


class Cursor:
    def __init__(self, cursor: sqlite3.Cursor) -> None:
        self._cursor = cursor

    @property
    def rowcount(self) -> int:
        return int(self._cursor.rowcount)

    async def fetchone(self):
        return self._cursor.fetchone()

    async def fetchall(self):
        return self._cursor.fetchall()

    async def close(self) -> None:
        self._cursor.close()


class Connection:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row

    @property
    def row_factory(self):
        return self._conn.row_factory

    @row_factory.setter
    def row_factory(self, value) -> None:
        self._conn.row_factory = value

    async def execute(self, sql: str, parameters: Iterable[Any] = ()):
        return Cursor(self._conn.execute(sql, tuple(parameters)))

    async def executemany(self, sql: str, seq_of_parameters: Iterable[Iterable[Any]]):
        normalized = [tuple(params) for params in seq_of_parameters]
        self._conn.executemany(sql, normalized)

    async def commit(self) -> None:
        self._conn.commit()

    async def rollback(self) -> None:
        self._conn.rollback()

    async def close(self) -> None:
        self._conn.close()

    async def __aenter__(self) -> "Connection":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._conn.close()


def connect(db_path: str) -> Connection:
    return Connection(db_path)
