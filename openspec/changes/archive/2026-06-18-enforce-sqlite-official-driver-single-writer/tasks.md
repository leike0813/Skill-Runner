# Tasks

- [x] Add OpenSpec delta specs for official `aiosqlite`, single-writer handles, and management hot-path behavior.
- [x] Add SQLite handle registry with per-DB long-lived connection and operation lock.
- [x] Route `RunStoreDatabase.connect()` through the registry.
- [x] Migrate engine status persistence to registry while keeping request getters memory-only.
- [x] Migrate process lease and durable auth stores away from direct `sqlite3.connect()`.
- [x] Add app shutdown cleanup for SQLite handles.
- [x] Add/update focused tests and static regression guards.
- [x] Run targeted pytest and OpenSpec validation.
