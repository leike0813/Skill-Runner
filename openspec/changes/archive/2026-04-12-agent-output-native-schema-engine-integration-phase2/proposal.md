## Why

Phase 1 introduced a stable run-scoped target output schema artifact, but Claude and Codex still treat that artifact as passive audit data. The engine command layer does not yet consume the schema natively, which leaves the execution path dependent on prompt-only guidance even when the CLI supports schema-constrained output.

This phase closes that gap by wiring the materialized schema artifact into the native headless CLI arguments for Claude and Codex, while keeping the outer orchestrator fallback and repair behavior unchanged.

## What Changes

- Add a dedicated engine-dispatch change for native schema CLI integration.
- Make Claude headless start/resume dispatch use `--output-format json` and `--json-schema <run-scoped-schema>`.
- Make Codex headless start/resume dispatch use `--output-schema <run-scoped-schema>`.
- Reuse the existing internal run option `__target_output_schema_relpath` as the only schema path input to command builders.
- Keep passthrough/harness commands, runtime repair logic, and external API shapes unchanged.
- Extend adapter and command-profile tests so schema flags and first-attempt spawn-command audit can be asserted directly.

## Capabilities

### New Capabilities
- `engine-native-output-schema-dispatch`: Headless Claude and Codex command dispatch consumes the run-scoped materialized output schema artifact.

### Modified Capabilities
- `engine-command-profile-defaults`: Claude headless defaults move from `stream-json` to `json` when native schema dispatch is enabled.
- `run-audit-contract`: First-attempt spawn command audit must remain sufficient to observe injected native schema arguments.

## Impact

- New OpenSpec change artifacts under `openspec/changes/agent-output-native-schema-engine-integration-phase2-2026-04-12/`
- Command-builder updates for `server/engines/claude/` and `server/engines/codex/`
- A small shared helper under `server/runtime/adapter/common/`
- Targeted command-profile and adapter tests for Claude/Codex
- No public API, runtime schema, FCMP/RASP, or orchestrator lifecycle changes in this phase
