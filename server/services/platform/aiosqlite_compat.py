from __future__ import annotations

import sqlite3
from typing import Any

import aiosqlite as _aiosqlite


Connection = _aiosqlite.Connection
Cursor = _aiosqlite.Cursor
Row = _aiosqlite.Row


class _RowConnection(sqlite3.Connection):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.row_factory = sqlite3.Row


def connect(db_path: str, **kwargs: Any) -> Connection:
    # Compatibility with the previous local shim. Concurrency control belongs in
    # the store layer, not in a per-connection driver wrapper.
    kwargs.pop("semaphore", None)
    kwargs.setdefault("factory", _RowConnection)
    return _aiosqlite.connect(db_path, **kwargs)


async def shutdown_executor() -> None:
    return None
