## 1. API and Data Contracts

- [x] 1.1 Add request/response models for two-step temporary skill workflow (create, upload/start, status)
- [x] 1.2 Add dedicated routes under `/v1/temp-skill-runs` and align status/error semantics with jobs API
- [x] 1.3 Add runtime option contract including `debug_keep_temp` and ensure temporary flow ignores cache

## 2. Temporary Skill Staging and Validation

- [x] 2.1 Add request-scoped storage paths for temporary skill package and extracted content
- [x] 2.2 Reuse/factor AutoSkill validation checks for temporary skill packages
- [x] 2.3 Enforce temporary package top-level directory and identity consistency checks
- [x] 2.4 Reject temporary packages with missing required files or invalid metadata contract
- [x] 2.5 Add package size-limit enforcement for temporary uploads
- [x] 2.6 Add zip extraction path-safety checks (reject zip-slip/absolute paths)

## 3. Orchestration Integration

- [x] 3.1 Add orchestration branch that executes runs with temporary skill path instead of registry lookup
- [x] 3.2 Ensure temporary flow does not mutate persistent `skills/` registry or discovery endpoints
- [x] 3.3 Keep run result/log/artifact behavior consistent with normal runs
- [x] 3.4 Ensure temporary-skill runs bypass cache lookup and cache write-back

## 4. Cleanup Lifecycle

- [x] 4.1 Implement immediate cleanup of temporary package/staging files on run terminal states
- [x] 4.2 Preserve run output files while removing only temporary skill content
- [x] 4.3 Add scheduled fallback cleanup for orphaned temporary skill files
- [x] 4.4 Implement warning-only behavior for immediate cleanup failures (no in-request retries)
- [x] 4.5 Implement debug-mode retention (`debug_keep_temp=true` skips immediate cleanup)

## 5. Tests and Documentation

- [x] 5.1 Add unit tests for temporary package validation and identity checks
- [x] 5.2 Add unit tests for package size and zip path-safety rejection
- [x] 5.3 Add unit tests for cleanup behavior, debug retention, and warning-only failure handling
- [x] 5.4 Add integration tests for two-step create+upload flow and terminal cleanup behavior
- [x] 5.5 Update API/test documentation with temporary skill workflow and constraints
