# Design

## DB State SSOT
`request_run_state`, `request_current_projection`, and `request_dispatch_state` are the request-bound state authority. File `.state` mirrors are removed from new lifecycle writes and from business read paths. Legacy no-layout helpers may continue reading or writing root `.state` files, but those helpers must be explicit and unreachable from normal request-bound API flows.

Management and observability list/detail read state from DB. File-state diagnostics may still report whether historical files exist, but they do not affect current status, error, pending owner, dispatch phase, or reply/cancel gating.

## SQLite Split
The split follows write-load domains:

- `runs.db`: low-frequency request/run metadata and workspace layout.
- `run_state.db`: high-frequency lifecycle state and dispatch state.
- `run_interactions.db`: user interaction, interaction history, interactive runtime, and resume tickets.
- `run_auth.db`: auth session and durable auth recovery state.
- `runtime_cache.db`: cache and skill package identity/cache records.
- Existing independent DBs remain or are corrected: process leases, engine status, skill installs, engine upgrades.

Each DB initializes its own PRAGMAs and schema. Existing `RunStore` methods remain the facade; store classes receive the DB handle for their domain.

## Migration
On initialization, if a split DB is empty and the legacy `runs.db` contains its tables, initialization performs best-effort table copy into the split DB. Copy failures are warnings and do not block startup. Old tables are not deleted from `runs.db`.

## Consistency
Cross-DB writes are ordered but not transactional across files. Core metadata is written before derived state/cache where the existing lifecycle already has that dependency. Failures remain visible through existing diagnostics and error handling.

## Indexing
Indexes are created only in the target DB file after the split. They cover list/status, state lookup, interaction reply/history, auth recovery, cache lookup, and cleanup paths.
