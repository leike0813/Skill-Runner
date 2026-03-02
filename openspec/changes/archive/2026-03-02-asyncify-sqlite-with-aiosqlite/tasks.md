## 1. OpenSpec Artifacts

- [x] 1.1 Create `proposal.md` for async sqlite migration scope and boundaries
- [x] 1.2 Create `specs/async-sqlite-store-access/spec.md`
- [x] 1.3 Create `design.md` with async migration and compatibility decisions

## 2. Dependency and Store Asyncification

- [x] 2.1 Add `aiosqlite` dependency in `pyproject.toml`
- [x] 2.2 Migrate `server/services/orchestration/run_store.py` to async `aiosqlite` with lazy init lock
- [x] 2.3 Migrate `server/services/skill/skill_install_store.py` to async `aiosqlite`
- [x] 2.4 Migrate `server/services/skill/temp_skill_run_store.py` to async `aiosqlite`
- [x] 2.5 Migrate `server/services/engine_management/engine_upgrade_store.py` to async `aiosqlite`

## 3. Runtime/Service Callchain Migration

- [x] 3.1 Update runtime observability contracts and source adapter/read facade to async store contracts
- [x] 3.2 Update run observability service callsites to await store access
- [x] 3.3 Update orchestration services (`job_orchestrator`, `run_job_lifecycle_service`, `run_interaction_service`, `run_cleanup_manager`) to await stores
- [x] 3.4 Update skill/engine services (`skill_package_manager`, `temp_skill_run_manager`, `engine_upgrade_manager`) to await stores

## 4. Router and Endpoint Migration

- [x] 4.1 Update `jobs.py` and `temp_skill_runs.py` async store calls
- [x] 4.2 Update `management.py`, `skill_packages.py`, `ui.py`, `engines.py` async store calls
- [x] 4.3 Ensure background tasks use async callables where migrated store access is required

## 5. Tests, Guards, and Validation

- [x] 5.1 Update store unit tests for async API (`test_run_store.py`, `test_skill_install_store.py`, `test_engine_upgrade_store.py`)
- [x] 5.2 Update service/router/runtime tests using async stubs or `AsyncMock`
- [x] 5.3 Add `tests/unit/test_sqlite_async_boundary.py` guard against `sqlite3` reintroduction in migrated stores
- [x] 5.4 Run required pytest suites and runtime contract tests
- [x] 5.5 Run required mypy checks for migrated modules
