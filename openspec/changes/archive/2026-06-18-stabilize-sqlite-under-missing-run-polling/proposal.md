# Proposal: stabilize sqlite under missing run polling

## Summary

High-frequency polling of missing run observability endpoints should keep returning 404 without destabilizing the backend. The current SQLite compatibility layer opens and uses `sqlite3` connections synchronously from async request paths, so dense missing-request polling can starve the event loop and amplify lock contention. This change moves SQLite operations behind a true async boundary, enables WAL and busy handling for the run store, and bounds per-database concurrency.

## Problem

The events/chat history routes correctly return 404 for unknown request IDs, but each request still resolves request metadata through the run store. In the fallback SQLite compatibility layer, `sqlite3.connect()`, query execution, fetching, commits, and closes happen synchronously on the event loop thread. Under rapid browser retry or mistaken client polling, this creates many short-lived blocking connections and can make unrelated management routes unresponsive.

## Goals

- Preserve existing 404 semantics for missing request/run observability calls.
- Prevent SQLite connect/query/fetch/commit/close from blocking the event loop.
- Make the run store more tolerant of short read/write contention using WAL, busy timeout, bounded retry, and a per-database concurrency gate.
- Avoid new runtime dependencies and keep existing store call sites largely unchanged.

## Non-Goals

- Do not create placeholder requests/runs for missing IDs.
- Do not change SSE creation behavior for missing runs.
- Do not add persistent negative-cache records.
- Do not replace SQLite with another database.
