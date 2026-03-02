## 1. OpenSpec Artifacts

- [x] 1.1 Create `proposal.md` with logging persistence and governance scope
- [x] 1.2 Create `specs/logging-persistence-controls/spec.md` with requirement scenarios
- [x] 1.3 Create `design.md` with configuration, rotation, quota, and fallback decisions

## 2. Configuration and Logging Runtime

- [x] 2.1 Add `SYSTEM.LOGGING` defaults and env mapping in `server/core_config.py`
- [x] 2.2 Refactor `server/logging_config.py` to timed daily rotation and configurable policy
- [x] 2.3 Add optional JSON formatter while keeping text as default
- [x] 2.4 Add quota enforcement utility for `data/logs` with oldest-first archive eviction
- [x] 2.5 Ensure setup fallback path (stream-only) and idempotent setup behavior

## 3. Tests and Guards

- [x] 3.1 Add `tests/unit/test_logging_config.py` for handler setup/idempotency/json/fallback
- [x] 3.2 Add `tests/unit/test_logging_quota_policy.py` for quota cleanup behavior

## 4. Documentation

- [x] 4.1 Update logging env/config sections in `docs/dev_guide.md`
- [x] 4.2 Update logging section in `docs/architecture_overview.md`
- [x] 4.3 Update logging section in `docs/test_specification.md`
- [x] 4.4 Remove references to `LOG_MAX_BYTES` semantics from docs

## 5. Validation

- [x] 5.1 Run `pytest tests/unit/test_logging_config.py tests/unit/test_logging_quota_policy.py`
- [x] 5.2 Run `pytest tests/unit/test_v1_routes.py tests/unit/test_ui_routes.py tests/unit/test_management_routes.py`
- [x] 5.3 Run `mypy --follow-imports=skip server/logging_config.py server/core_config.py`
