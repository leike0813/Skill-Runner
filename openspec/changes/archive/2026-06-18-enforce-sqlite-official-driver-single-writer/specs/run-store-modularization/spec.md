# run-store-modularization Delta

## ADDED Requirements

### Requirement: RunStoreDatabase MUST expose operation-scoped connections
`RunStoreDatabase.connect()` MUST provide an operation-scoped async context backed by the per-DB SQLite handle.

#### Scenario: Existing sub-store uses async with
- **WHEN** a sub-store enters `async with database.connect()`
- **THEN** it receives the DB file's shared `aiosqlite` connection
- **AND** the operation lock is held until the context exits
- **AND** exiting the context does not close the shared connection

### Requirement: SQLite handles MUST close during app shutdown
Runtime SQLite handles MUST be closed during app shutdown through a bounded cleanup path.

#### Scenario: Service shuts down after DB use
- **WHEN** application lifespan exits
- **THEN** the SQLite handle registry closes open connections
- **AND** cleanup timeout records diagnostics instead of blocking forever
