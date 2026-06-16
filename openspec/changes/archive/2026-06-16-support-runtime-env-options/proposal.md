## Why

Cascaded and automated skill runs sometimes need request-scoped environment values such as feature flags or provider-local knobs. Today callers can only influence subprocess environment through global engine/profile configuration, which either leaks across runs or is not recoverable for queued/retry/resume execution.

## What Changes

- Add `runtime_options.env` as a request-level object of environment variable names to string values.
- Validate env names and values with a safe allowlist and reject core process/path variables.
- Store raw env values only in a local per-request secret vault; persist only redacted projections in DB, API, status, and audit snapshots.
- Load vault env during run attempt preparation and inject it into the current adapter subprocess environment only.
- Keep `runtime_options.env` out of cache key construction.
- Delete env secret files during request/run cleanup.

## Capabilities

### New Capabilities
- `runtime-env-options`: Defines request-scoped environment variable injection, validation, redaction, vault persistence, execution injection, cache behavior, and cleanup.

### Modified Capabilities
- `interactive-job-api`: Adds `runtime_options.env` request semantics and validation errors.
- `run-audit-contract`: Requires audit/status/API projections to avoid raw env values.
- `run-store-modularization`: Adds a local secret vault contract for raw per-request env values.
- `engine-adapter-runtime-contract`: Requires adapter subprocess execution to apply run-local env without mutating global process state.

## Impact

- API: `POST /v1/jobs` accepts `runtime_options.env`.
- Persistence: request records and audit snapshots store redacted env projections; raw values are written to `data/run_secrets`.
- Runtime: attempt preparation reads the vault and passes internal `__runtime_env` to adapters.
- Cleanup: expired/manual cleanup removes related secret files.
- Tests/docs: add focused unit/regression coverage and document the new runtime option.
