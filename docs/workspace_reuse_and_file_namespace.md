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

## File Bindings

Reused workspaces can materialize an existing workspace file as the current run's file input:

```json
{
  "input": {
    "artifact_file": "inputs/artifact_file/file.json"
  },
  "runtime_options": {
    "workspace": {
      "mode": "reuse",
      "request_id": "previous-request-id",
      "file_bindings": [
        {
          "input_key": "artifact_file",
          "source_request_id": "emitting-request-id",
          "source_path": "runtime/file.json",
          "target_path": "inputs/artifact_file/file.json"
        }
      ]
    }
  }
}
```

`source_request_id` must resolve to a succeeded request in the same physical workspace as `workspace.request_id`.
`source_path` is workspace-relative. `target_path` is uploads-relative, and `input[input_key]` must equal that target path.
Both paths must be non-empty relative file paths and must not be absolute, `.`, `..`, traversal paths, or directories.

The backend materializes each binding into staging uploads before manifest and cache-key calculation.
For upload requests, the uploaded zip is extracted first and bindings are materialized afterward, so a binding overwrites a zip entry at the same `target_path`.
On Windows the backend copies the file. On other platforms it tries a hard link first and falls back to copying.

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
uploads/.interaction-replies/<safeSkillId>.<n>/<interaction-id>/<receipt-token>/
```

`result/result.json` is only a legacy fallback for historical runs. New reused-workspace runs do not maintain it as a latest alias.

Managed interaction reply files belong to the current logical request namespace even when the physical workspace is reused. Continuations expose only workspace-relative POSIX paths. The reserved subtree is readable by the resumed agent through those paths but excluded from run explorer, preview, debug bundle, and filesystem snapshot surfaces.

## Cache Lineage

Reused-workspace runs include the source request's workspace output token in their cache key. This prevents a downstream step from reusing a cached result produced from a different upstream workspace state, while still allowing a fully identical chain to benefit from cache hits.
Materialized file bindings are also included in the input manifest, so different bound file contents produce different cache identities.
