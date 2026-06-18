# Stabilize DB SSOT And Split Write Loads

## Summary
Make DB state the only current truth for request-bound run state and split SQLite files by write-load domain so high-frequency lifecycle writes no longer contend with unrelated runtime metadata.

## Problem
The restored baseline is stable enough to execute runs, but run state still has two active representations: DB rows and `.state/*.json` files. Observability and management paths can still read state files, which creates drift risk and extra filesystem work. At the same time, one SQLite file still hosts lifecycle state, interaction/session metadata, auth recovery, cache tables, process leases, engine status, and install tracking. WAL improves read/write overlap but does not remove single-file write-lock contention.

## Goals
- Use DB tables as the sole request-bound state and dispatch SSOT.
- Stop writing and reading `.state/<namespace>/state.json` and `.state/<namespace>/dispatch.json` for new request-bound runs.
- Split SQLite files by write-load domain, not by whether a table is "core" or "edge".
- Add indexes after the split, on the actual query paths in each DB file.

## Non-Goals
- Switch the default backend to PostgreSQL.
- Reintroduce persistence backend abstraction.
- Change public API response field names.
- Migrate or support historical no-layout data beyond explicit legacy/maintenance helpers.
