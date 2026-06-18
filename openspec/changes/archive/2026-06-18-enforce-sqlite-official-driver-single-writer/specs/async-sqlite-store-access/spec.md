# async-sqlite-store-access Delta

## ADDED Requirements

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
