# run-store-modularization Delta

## ADDED Requirements

### Requirement: Run store SQLite configuration MUST be centralized in RunStoreDatabase
The run store MUST centralize SQLite connection gating and database-level PRAGMA configuration in `RunStoreDatabase` rather than duplicating it across request, run, cache, interaction, state, or auth stores.

#### Scenario: Request store opens a connection
- **WHEN** a modular run store component opens a connection through `RunStoreDatabase.connect()`
- **THEN** the connection participates in the per-database concurrency gate
- **AND** the component does not implement its own SQLite connection throttling.

#### Scenario: Run store database initializes schema
- **WHEN** `RunStoreDatabase.init_db()` prepares schema
- **THEN** it applies WAL and synchronous mode configuration before table creation and migration
- **AND** modular stores rely on that shared configuration.
