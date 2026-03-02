## 1. Shared Reset Core

- [x] 1.1 Extract reset target planning and execution logic from `scripts/reset_project_data.py` into a reusable service module
- [x] 1.2 Keep CLI script behavior compatible by switching script internals to call the shared service module
- [x] 1.3 Add in-process execution lock to prevent concurrent destructive reset runs

## 2. Management API Endpoint

- [x] 2.1 Add management reset request/response models in `server/models/management.py` and export in `server/models/__init__.py`
- [x] 2.2 Add `POST /v1/management/system/reset-data` in `server/routers/management.py` with strict confirmation validation
- [x] 2.3 Support `dry_run` and include-option flags aligned with `reset_project_data.py`
- [x] 2.4 Return structured result payload with target list and deleted/missing/recreated counters

## 3. Management UI Dangerous Action

- [x] 3.1 Add a distinct “Danger Zone” section on `/ui` with high-visibility destructive-action styling
- [x] 3.2 Implement confirmation modal requiring manual confirmation text input before enabling execute
- [x] 3.3 Wire modal submit to management reset endpoint and pass selected include flags plus confirmation payload
- [x] 3.4 Render success/failure result feedback including summary counters and impact hint

## 4. Tests

- [x] 4.1 Add route tests for management reset endpoint: confirmation rejected, dry-run no side effects, execute success
- [x] 4.2 Add UI tests for danger zone visibility, modal confirmation gating, and request trigger behavior
- [x] 4.3 Add service-level tests to verify target parity and execution parity between script and API paths

## 5. Validation and Docs

- [x] 5.1 Update `docs/dev_guide.md` with management reset endpoint usage and safety warning
- [x] 5.2 Run tests in DataProcessing env:
- [x] 5.3 `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_management_routes.py tests/unit/test_ui_routes.py`
- [x] 5.4 Run type checks in DataProcessing env:
- [x] 5.5 `conda run --no-capture-output -n DataProcessing python -u -m mypy --follow-imports=skip server/routers/management.py server/routers/ui.py server/models/management.py`
