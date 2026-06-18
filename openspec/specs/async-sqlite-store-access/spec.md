# async-sqlite-store-access Specification

## Purpose
定义 SQLite store 异步化后的访问约束、调用链 await 语义、统一 Jobs API 下 installed/temp_upload 持久化行为以及防止同步 sqlite 回归的测试门禁。

## Requirements
### Requirement: SQLite-backed stores MUST use asynchronous aiosqlite operations
The system MUST implement SQLite-backed stores using `aiosqlite` APIs and MUST NOT use synchronous `sqlite3` APIs in migrated store implementations.

#### Scenario: Run store executes request mutation
- **WHEN** orchestration persists request/run/cache/interaction records
- **THEN** SQLite operations are executed via awaited `aiosqlite` calls
- **AND** no synchronous `sqlite3.connect` call is used in migrated store modules

### Requirement: All callsites of migrated stores MUST await asynchronous methods
The system MUST update all callsites that invoke migrated stores to use `await` end-to-end.

#### Scenario: Router creates run and checks cache
- **WHEN** `/jobs` executes installed or `temp_upload` request creation and cache lookup
- **THEN** the router awaits each store call
- **AND** request semantics and HTTP responses remain backward compatible

### Requirement: Runtime observability and source adapter ports MUST support async contracts
The system MUST expose async contracts for run-source and run-observability store-dependent operations.

#### Scenario: Read run status and stream history
- **WHEN** run read facade and source adapter resolve request/run metadata
- **THEN** they await async store methods through async protocol contracts
- **AND** returned history/event payload semantics remain unchanged

### Requirement: Store initialization and migrations MUST remain idempotent under concurrent first access
The system MUST ensure DB table creation and migration are safe under concurrent async first access.

#### Scenario: Concurrent first requests hit an uninitialized DB
- **WHEN** multiple coroutines call the same store before initialization completes
- **THEN** initialization runs safely and idempotently
- **AND** no schema corruption or conflicting migration side effects occur

### Requirement: Behavior of run/install/temp/upgrade flows MUST remain backward compatible
The system MUST preserve existing state transitions and persistence semantics while changing I/O execution style.

#### Scenario: Interactive pending/reply and timeout flow
- **WHEN** an interactive run enters waiting state and receives a reply or auto decision
- **THEN** status transitions, error codes, and interaction persistence match prior behavior

#### Scenario: Skill install and engine upgrade task tracking
- **WHEN** install or upgrade tasks are created and updated
- **THEN** persisted task/install statuses and response payloads remain unchanged

### Requirement: CI MUST prevent regression to synchronous sqlite usage in migrated stores
The system MUST include tests that fail when migrated store modules reintroduce synchronous sqlite access.

#### Scenario: Developer introduces sqlite3 in migrated store
- **WHEN** CI runs unit checks
- **THEN** regression guard tests fail
- **AND** the change is blocked until async store boundary is restored

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

### Requirement: SQLite runtime stores MUST use official aiosqlite handles

Runtime SQLite stores MUST use official `aiosqlite` connections managed by the runtime handle registry.

#### Scenario: Store opens SQLite connection
- **WHEN** a runtime store needs SQLite access
- **THEN** it obtains a connection through the handle registry
- **AND** it MUST NOT create a custom executor/retry wrapper around `sqlite3`

### Requirement: Each SQLite DB file MUST have one process-local operation queue

The system MUST maintain at most one process-local long-lived `aiosqlite` connection and operation lock per resolved DB path.

#### Scenario: Multiple stores use the same DB file
- **WHEN** multiple stores operate on the same SQLite file
- **THEN** their operations share the same handle and operation lock
- **AND** operations against that DB file execute serially within the process

### Requirement: Production hot paths MUST NOT synchronously open SQLite

Production request/runtime hot paths MUST NOT call `sqlite3.connect()` directly.

#### Scenario: Management UI reads engine metadata
- **WHEN** management/UI routes render engine summaries
- **THEN** they read cached in-memory engine status
- **AND** they do not synchronously open SQLite from the event-loop thread
