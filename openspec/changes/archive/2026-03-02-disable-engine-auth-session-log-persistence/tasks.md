## 1. OpenSpec Artifacts

- [x] 1.1 Create `proposal.md` describing sensitive auth log persistence risks and scope
- [x] 1.2 Create delta spec `specs/engine-auth-observability/spec.md`
- [x] 1.3 Create `design.md` with default-off + opt-in persistence strategy

## 2. Implementation

- [x] 2.1 Add `SYSTEM.ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED` in `server/core_config.py`
- [x] 2.2 Add `NoopAuthLogWriter` in `server/runtime/auth/log_writer.py`
- [x] 2.3 Inject writer by config in `server/services/engine_management/engine_auth_flow_manager.py`
- [x] 2.4 Ensure session snapshot behavior remains compatible when log persistence is disabled
- [x] 2.5 Keep opt-in mode backward compatible with existing directory/file layout

## 3. Tests

- [x] 3.1 Update/add tests for default disabled mode (no `engine_auth_sessions` directories created)
- [x] 3.2 Update/add tests for opt-in enabled mode (existing files still created)
- [x] 3.3 Run auth core/unit regressions:
  - `tests/unit/test_auth_log_writer.py`
  - `tests/unit/test_engine_auth_flow_manager.py`
  - `tests/unit/test_management_routes.py`
  - `tests/unit/test_ui_routes.py`

## 4. Docs & Tooling

- [x] 4.1 Update `docs/containerization.md` logging paths to mark engine auth logs as optional/debug-only
- [x] 4.2 Update `docs/dev_guide.md` env var reference for `ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED`
- [x] 4.3 Confirm `scripts/reset_project_data.py` keeps `--include-engine-auth-sessions` optional cleanup flag

## 5. Validation

- [x] 5.1 `openspec validate disable-engine-auth-session-log-persistence --type change`
- [x] 5.2 Execute required pytest suites in DataProcessing env
