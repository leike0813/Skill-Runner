# async-sqlite-store-access Delta

## MODIFIED Requirements

### Requirement: SQLite-backed stores MUST use asynchronous aiosqlite operations
The system MUST implement SQLite-backed stores using awaited compatibility operations and MUST NOT execute synchronous SQLite connect, query, fetch, commit, rollback, or close operations on the request event loop thread.

#### Scenario: Run store resolves a missing request under polling load
- **WHEN** observability routes repeatedly query an unknown `request_id`
- **THEN** each SQLite operation runs behind an async boundary
- **AND** synchronous SQLite I/O does not block the event loop thread
- **AND** the route can still return 404.

### Requirement: Store initialization and migrations MUST remain idempotent under concurrent first access
The system MUST ensure DB table creation and migration are safe under concurrent async first access, and MUST configure the run store SQLite database for contention-tolerant local access.

#### Scenario: Concurrent first requests hit an uninitialized DB
- **WHEN** multiple coroutines call the same store before initialization completes
- **THEN** initialization runs safely and idempotently
- **AND** the run store enables WAL and normal synchronous mode before schema mutations
- **AND** no schema corruption or conflicting migration side effects occur.

## ADDED Requirements

### Requirement: SQLite compatibility layer MUST tolerate short lock contention
The SQLite compatibility layer MUST configure a busy timeout and retry short `SQLITE_BUSY` or `SQLITE_LOCKED` failures with bounded backoff before surfacing the original error.

#### Scenario: A transient lock resolves during retry
- **GIVEN** SQLite raises a locked database operational error for an operation
- **WHEN** the contention clears before the retry budget is exhausted
- **THEN** the operation succeeds
- **AND** callers observe the normal result.

#### Scenario: A persistent lock exceeds retry budget
- **GIVEN** SQLite continues raising a locked database operational error
- **WHEN** the retry budget is exhausted
- **THEN** the original operational error is raised
- **AND** the retry loop terminates.

### Requirement: Run store MUST bound concurrent SQLite connections per database
The run store database wrapper MUST limit active SQLite compatibility connections for a single database to a bounded default.

#### Scenario: Many requests poll the same missing run
- **WHEN** many coroutines concurrently query the same run store database
- **THEN** the run store gates active SQLite connections
- **AND** it avoids unbounded connection storms.
