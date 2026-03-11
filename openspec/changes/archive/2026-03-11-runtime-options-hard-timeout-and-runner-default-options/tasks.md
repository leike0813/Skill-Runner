## 1. OpenSpec Artifacts

- [x] 1.1 Create proposal/design/tasks and delta specs for this change.

## 2. Runtime Option Contract

- [x] 2.1 Add `hard_timeout_seconds` to runtime option allowlist and validation.
- [x] 2.2 Extend runner manifest schema/model with `runtime.default_options`.

## 3. Runtime Option Composition

- [x] 3.1 Add shared helper to compose `effective_runtime_options` from skill defaults + request options.
- [x] 3.2 Apply helper in `/v1/jobs` installed flow.
- [x] 3.3 Apply helper in `/v1/jobs/{request_id}/upload` temp-upload flow and persist updated effective options.

## 4. Warning and Observability

- [x] 4.1 Emit `SKILL_RUNTIME_DEFAULT_OPTION_IGNORED` for invalid default options.
- [x] 4.2 Surface warning to lifecycle warnings/diagnostic stream via existing run lifecycle aggregation.

## 5. Docs and Tests

- [x] 5.1 Update API and file protocol docs for new option and manifest field.
- [x] 5.2 Add/update unit and integration tests for hard timeout option and runner defaults merge.
