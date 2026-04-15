## Why

Phase 0A fixed the target SSOT for JSON-only output contracts, but the runtime still has no stable run-scoped schema artifact to reuse across prompt injection, audit, and future engine CLI enforcement. Output schema guidance is still derived ad hoc at patch time, which means there is no single materialized machine source per run.

## What Changes

- Add a run-scoped output schema builder/materialization service that derives both machine-readable schema and prompt-facing markdown from the same JSON Schema source.
- Materialize stable artifacts under `.audit/contracts/target_output_schema.json` and `.audit/contracts/target_output_schema.md`.
- Generate an `interactive` union machine schema artifact, while keeping current ask-user prompt compatibility for pending turns in this phase.
- Refactor skill patching so runtime-injected output schema guidance consumes materialized markdown instead of re-reading raw `output.schema.json`.
- Propagate stable schema artifact relative paths into internal `run_options` and first-attempt `request_input.json` audit fields.

## Capabilities

### New Capabilities
- `run-output-schema-materialization`: Each run materializes a stable target output schema artifact pair for machine/audit use and prompt guidance reuse.

### Modified Capabilities
- `skill-patch-modular-injection`: Output schema injection now comes from run-scoped materialized markdown instead of ad hoc raw-schema rendering at patch time.

## Impact

- New orchestration service for run-scoped output schema materialization.
- Updated run bootstrapper, job lifecycle wiring, and skill patching interface.
- New unit tests for schema materialization, plus updated patcher/bootstrapper coverage.
- No HTTP API, FCMP, RASP, repair-loop, or completion/waiting semantic changes in this phase.
