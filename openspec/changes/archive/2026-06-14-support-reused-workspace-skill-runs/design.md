## Context

Skill Runner currently treats `run_id` as both the logical execution identity and the physical workspace directory name under `data/runs/<run_id>/`. Runner-owned files are written to fixed paths such as `result/result.json`, `.state/state.json`, and `.audit/request_input.json`.

Cascaded skill execution needs a later request to run in a previous request's workspace. Fixed runner-owned paths would overwrite earlier step records, so the runtime needs per-run namespaces inside the shared workspace and persistent records of actual paths.

## Goals / Non-Goals

**Goals:**
- Allow `POST /v1/jobs` callers to request workspace reuse with `runtime_options.workspace.mode="reuse"` and a source `request_id`.
- Keep every skill execution as a distinct logical run with its own `run_id`.
- Persist actual runner-owned result/input-manifest paths for each run.
- Preserve cache correctness for reused-workspace chains by including upstream workspace lineage in the cache key.
- Keep legacy fixed-path runs readable.

**Non-Goals:**
- Supporting concurrent active writers in one workspace.
- Accepting public `run_id` workspace references.
- Maintaining `result/result.json` as a latest alias for new runs.
- Adding a workflow manifest field for namespace allocation.

## Decisions

1. **Use `request_id` as the public reuse handle.**  
   A request is the client-visible unit of workflow chaining and already maps to the effective run, cache result, and status. Direct `run_id` reuse is rejected to avoid exposing internal workspace/run coupling.

2. **Introduce physical workspace metadata while preserving logical `run_id`.**  
   New store fields track `workspace_id`, `workspace_dir`, `workspace_namespace`, `workspace_source_request_id`, `result_path`, `input_manifest_path`, `workspace_input_token`, and `workspace_output_token`. Existing callers continue to identify runs by `run_id`; layout resolution uses the persisted workspace metadata.

3. **Use provider-owned namespaces for runner-owned files.**  
   Each new logical run in a workspace receives `<safeSkillId>.<n>`, using the upstream safe segment rule. Result and input-manifest files are written under that namespace. Retry/resume of the same logical run reuses the existing namespace.

4. **Use lineage-aware cache keys.**  
   Reused-workspace requests include the source request's `workspace_output_token` as `workspace_input_token` in the cache key. If an upstream step hits cache, it exposes the cached output token, allowing downstream identical chains to hit cache as well.

5. **Read actual paths first, legacy paths second.**  
   Result APIs, bundle generation, and diagnostics read the persisted actual result path. If absent, they fall back to `result/result.json` for historical runs.

## Risks / Trade-offs

- [Risk] Some runtime code still assumes `run_dir.name == run_id`. → Mitigation: introduce a layout resolver and update read/write paths touched by result, state, dispatch, audit, and observability.
- [Risk] Shared workspace cleanup could remove files needed by another request. → Mitigation: keep cleanup keyed by physical workspace ownership and only delete once no records reference the workspace.
- [Risk] Cache lineage token may miss package-owned side effects outside runner-owned files. → Mitigation: token is derived from upstream result/cache identity, matching the supported serial workflow contract; arbitrary concurrent external mutation remains out of scope.
- [Risk] Legacy tests expect fixed paths. → Mitigation: update tests to assert actual recorded paths and add explicit legacy fallback coverage.
