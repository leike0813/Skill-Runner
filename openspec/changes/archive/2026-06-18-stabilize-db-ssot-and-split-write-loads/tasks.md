# Tasks

- [x] Add OpenSpec deltas for DB SSOT, file contract, and dispatch state.
- [x] Add split SQLite DB configuration and domain database handles.
- [x] Move state/dispatch tables to `run_state.db` and stop request-bound `.state` writes.
- [x] Move interaction/runtime/resume tables to `run_interactions.db`.
- [x] Move auth tables to `run_auth.db`.
- [x] Move cache/package cache tables to `runtime_cache.db`.
- [x] Ensure process lease, engine status, skill install, and engine upgrade stores use independent DB files.
- [x] Make management/observability state reads DB-first and remove `.state` state decisions.
- [x] Add split-DB indexes and best-effort legacy copy.
- [x] Run targeted tests and OpenSpec validation.
