# async-sqlite-store-access Specification

## Purpose
定义 SQLite store 异步化后的访问约束、调用链 await 语义和回归门禁。

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
- **WHEN** `/jobs` or `/temp-skill-runs` executes request creation and cache lookup
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
