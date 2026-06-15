# Workspace Reuse and File Namespaces

Skill Runner supports serial cascaded skill execution by allowing a later request to reuse a previous successful request's workspace.

## Request Contract

Clients request reuse through `runtime_options.workspace`:

```json
{
  "runtime_options": {
    "workspace": {
      "mode": "reuse",
      "request_id": "previous-request-id"
    }
  }
}
```

Only `request_id` is accepted as the public reuse handle. The source request must exist, be bound to a run, have succeeded, and still have an available workspace.

## Workspace Identity

Each skill execution keeps its own logical `run_id`. When workspace reuse is requested, the new run shares the source request's physical workspace while receiving its own run record and runner-owned file namespace.

## Runner-Owned Namespaces

Every logical run in a workspace receives a provider-owned namespace:

```text
<safeSkillId>.<n>
```

`safeSkillId` is produced by trimming the skill id, replacing consecutive characters outside `[A-Za-z0-9._-]` with `-`, trimming leading/trailing `-`, and falling back to `skill` when empty. The counter is 1-based per safe skill id in the workspace.

New runner-owned files use actual persisted paths:

```text
result/<safeSkillId>.<n>/result.json
.audit/<safeSkillId>.<n>/input_manifest.json
```

`result/result.json` is only a legacy fallback for historical runs. New reused-workspace runs do not maintain it as a latest alias.

## Cache Lineage

Reused-workspace runs include the source request's workspace output token in their cache key. This prevents a downstream step from reusing a cached result produced from a different upstream workspace state, while still allowing a fully identical chain to benefit from cache hits.
