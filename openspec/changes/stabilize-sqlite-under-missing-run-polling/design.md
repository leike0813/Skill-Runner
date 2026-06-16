# Design: stabilize sqlite under missing run polling

## Async SQLite Boundary

`server.services.platform.aiosqlite_compat` remains the compatibility module used by migrated stores. Its public shape stays compatible with existing call sites:

- `connect(path)` returns an async context manager.
- `Connection.execute`, `executemany`, `commit`, `rollback`, and `close` remain awaitable.
- `Cursor.fetchone`, `fetchall`, and `close` remain awaitable.

The implementation opens connections lazily in `__aenter__` or on first operation. Each compatibility connection owns a dedicated single-worker executor. SQLite operations run through that executor under a per-connection async lock, so synchronous SQLite calls do not execute on the request event loop thread and a SQLite connection does not drift across multiple worker threads.

Each connection is configured with:

- `timeout=5.0`
- `check_same_thread=False`
- `row_factory=sqlite3.Row`
- `PRAGMA busy_timeout = 5000`
- `PRAGMA foreign_keys = ON`

Short lock contention errors are retried with bounded exponential backoff. Persistent lock errors keep raising the original `sqlite3.OperationalError`.

## Run Store Database

`RunStoreDatabase` owns a lightweight per-database semaphore with a default limit of 16 active compatibility connections. The semaphore is passed to `aiosqlite_compat.connect()` to prevent connection storms while preserving the existing `async with database.connect()` call pattern.

During initialization, the run store applies database-level PRAGMAs before schema work:

- `PRAGMA journal_mode=WAL`
- `PRAGMA synchronous=NORMAL`
- `PRAGMA busy_timeout = 5000`

This reduces read/write blocking and makes short contention less likely to escape to HTTP routes.

## Observability Semantics

Missing request and missing run handling remains unchanged:

- `/v1/jobs/{request_id}/events/history` returns 404 for missing requests.
- `/v1/jobs/{request_id}/chat/history` returns 404 for missing requests.
- Missing run SSE routes do not create a stream.
- No placeholder request or run records are written.

The stability improvement is achieved below the route layer.
