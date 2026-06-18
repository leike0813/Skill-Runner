# Tasks

- [x] Create OpenSpec proposal/design/spec/tasks artifacts.
- [x] Update SQLite compat layer to run connect/execute/fetch/commit/close off the event loop thread.
- [x] Add connection busy timeout, foreign keys, row factory preservation, and bounded retry for locked database errors.
- [x] Add run store WAL/synchronous initialization PRAGMAs.
- [x] Add a per-run-store database concurrency gate.
- [x] Add unit coverage for async boundary, row behavior, retry, WAL, and busy timeout.
- [x] Add regression coverage for concurrent missing-run history polling staying 404 while management routes remain responsive.
- [x] Run targeted pytest validation.
- [x] Run `openspec validate stabilize-sqlite-under-missing-run-polling --strict`.
