## Why

Skill Runner needs to support cascaded skill execution where a later skill can reuse the workspace produced by a previous skill. The current fixed runner-owned files, such as `result/result.json` and `.audit/request_input.json`, collide when multiple logical runs share one physical workspace.

## What Changes

- Add request-level workspace reuse through `runtime_options.workspace.mode="reuse"` with `request_id` as the only public reuse handle.
- Decouple logical run identity from physical workspace identity so each skill run keeps its own `run_id` while sharing a workspace directory when requested.
- Allocate provider-owned file namespaces per skill run using `<safeSkillId>.<n>`.
- Persist actual runner-owned paths for terminal result and input manifest instead of deriving fixed paths.
- Include upstream workspace lineage in cache keys so reused-workspace steps remain cacheable without reading from the wrong workspace state.
- Expose workspace/result/input-manifest diagnostics in status and management responses.
- Update runtime docs to describe workspace reuse, namespaced runner-owned files, and legacy fixed-path fallback.

## Capabilities

### New Capabilities
- `reused-workspace-skill-runs`: Defines workspace reuse semantics, namespace allocation, lineage-aware cache behavior, and diagnostics for cascaded skill runs.

### Modified Capabilities
- `interactive-job-api`: Adds `runtime_options.workspace.mode="reuse"` and validates source request constraints.
- `run-file-contract`: Replaces fixed new-run runner-owned result/input-manifest paths with actual namespaced paths.
- `run-store-modularization`: Persists workspace identity, namespace, actual paths, and workspace lineage tokens.
- `run-current-projection`: Surfaces workspace and actual path diagnostics to consumers.

## Impact

- API: `POST /v1/jobs` accepts `runtime_options.workspace` reuse intent.
- Persistence: run/request records need workspace metadata and lineage token fields with legacy fallback.
- Runtime filesystem: terminal result and input manifest writes move to namespaced paths.
- Cache: cache key construction gains an optional workspace lineage factor.
- Docs/tests: OpenSpec deltas, `docs/` runtime docs, unit tests, and API/integration tests must be updated.
