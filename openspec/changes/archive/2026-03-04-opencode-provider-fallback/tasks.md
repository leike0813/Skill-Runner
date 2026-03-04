## 1. Change Artifacts

- [x] 1.1 Draft proposal/design/tasks for the engine-specific `opencode` provider fallback change.
- [x] 1.2 Add delta specs for `interactive-job-api` and `job-orchestrator-modularization`.

## 2. Orchestration Provider Fallback

- [x] 2.1 Resolve canonical `opencode` provider from request-side `engine_options.model` before creating pending auth.
- [x] 2.2 Update auth orchestration to prefer canonical provider over detection provider for `opencode`.
- [x] 2.3 Emit a clear diagnostic when `opencode` high-confidence auth cannot resolve provider from the request model.

## 3. Protocol and Regression Coverage

- [x] 3.1 Keep FCMP auth challenge provider aligned with canonical pending auth payload.
- [x] 3.2 Add regression coverage for null detection provider, conflicting provider hint, and unresolved model cases.
