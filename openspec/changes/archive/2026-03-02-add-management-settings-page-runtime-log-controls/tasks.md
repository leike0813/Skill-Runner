## 1. Change Artifacts

- [x] 1.1 Create proposal, design, tasks, and spec files for `add-management-settings-page-runtime-log-controls`

## 2. Runtime Settings Persistence

- [x] 2.1 Add `server/assets/configs/system_settings.bootstrap.json` for UI-editable logging defaults
- [x] 2.2 Add `server/services/platform/system_settings_service.py` with bootstrap initialization, validation, read, and atomic write
- [x] 2.3 Add `SYSTEM.SETTINGS_FILE` and `SYSTEM.SETTINGS_BOOTSTRAP_FILE` config paths in `server/core_config.py`

## 3. Logging Reload

- [x] 3.1 Refactor `server/logging_config.py` to resolve editable logging fields from `SystemSettingsService`
- [x] 3.2 Keep non-UI logging fields on existing config/env entrypoints
- [x] 3.3 Add explicit logging reload/reapply entrypoint with handler reset and idempotency

## 4. Management API

- [x] 4.1 Add management settings request/response models in `server/models/management.py` and export them
- [x] 4.2 Add `GET /v1/management/system/settings`
- [x] 4.3 Add `PUT /v1/management/system/settings` with strict writable-field validation
- [x] 4.4 Normalize `include_engine_auth_sessions` to `False` when auth log persistence is disabled

## 5. Management UI

- [x] 5.1 Add `/ui/settings` route and template context wiring in `server/routers/ui.py`
- [x] 5.2 Remove the data reset danger zone from `server/assets/templates/ui/index.html`
- [x] 5.3 Add a Settings navigation card to the home page
- [x] 5.4 Add settings page templates/partials for logging settings and reset danger zone
- [x] 5.5 Hide engine auth session cleanup controls when the feature is disabled

## 6. Data Reset Integration

- [x] 6.1 Include `data/system_settings.json` in reset targets
- [x] 6.2 Gate engine auth session reset targets by effective feature capability

## 7. Tests and Docs

- [x] 7.1 Add `tests/unit/test_system_settings_service.py`
- [x] 7.2 Update `tests/unit/test_logging_config.py`
- [x] 7.3 Update `tests/unit/test_management_routes.py`
- [x] 7.4 Update `tests/unit/test_ui_routes.py`
- [x] 7.5 Update `tests/unit/test_data_reset_service.py`
- [x] 7.6 Update `docs/dev_guide.md`, `docs/architecture_overview.md`, and `docs/containerization.md`

## 8. Validation

- [x] 8.1 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_system_settings_service.py tests/unit/test_logging_config.py tests/unit/test_management_routes.py tests/unit/test_ui_routes.py tests/unit/test_data_reset_service.py`
- [x] 8.2 `conda run --no-capture-output -n DataProcessing python -u -m mypy --follow-imports=skip server/services/platform/system_settings_service.py server/logging_config.py server/routers/management.py server/routers/ui.py server/models/management.py`
