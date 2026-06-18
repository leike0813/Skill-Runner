# Design

## Workspace Identity
`run_id` remains a logical execution identity. New non-reuse requests allocate `workspace_id = run_id` and create `data/workspaces/<workspace_id>`. Reuse requests keep a new `run_id`, but inherit the source request's `workspace_id` and `workspace_dir`.

`data/runs/<run_id>` is no longer created for new request-bound runs. It remains a legacy fallback for records that predate persisted workspace metadata.

## Layout Resolution
Request-bound lifecycle stages resolve layout in this order:

1. Read the request/run record.
2. If `workspace_dir` and `workspace_namespace` exist and the directory is present, use that physical workspace.
3. Fall back to `data/runs/<run_id>` only for legacy no-layout records.

This applies to preparation, execution, finalization, auth, interaction, observability, management, and recovery flows.

## Runner-Owned Files
All runner-owned paths are rooted at physical `workspace_dir`:

- `result/<namespace>/result.json`
- `.audit/<namespace>/input_manifest.json`
- `.audit/<namespace>/contracts/target_output_schema.json`
- `.state/<namespace>/state.json`
- `.state/<namespace>/dispatch.json`
- `bundle/<namespace>/run_bundle*.zip`

The short-term code may still call this root `run_dir`; its value must be the physical workspace for new request-bound runs.

## Cleanup
Run cleanup deletes the logical run record first, then checks whether any remaining run references the same `workspace_id` or `workspace_dir`. The physical workspace is removed only when no references remain. Legacy `data/runs/<run_id>` cleanup remains best-effort; old symlinks are unlinked rather than recursively deleting their targets.

## Compatibility
Historical runs without layout metadata remain readable through `data/runs/<run_id>`. The change does not introduce a migration.
