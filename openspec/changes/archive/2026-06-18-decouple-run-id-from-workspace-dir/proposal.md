# Decouple Run ID From Workspace Dir

## Summary
Stop treating `data/runs/<run_id>` as the physical execution root for new request-bound runs. A run id is a logical identity; the physical workspace is `data/workspaces/<workspace_id>` and may be shared by sequential workspace-reuse runs.

## Problem
Workspace reuse previously used a `data/runs/<new_run_id>` symlink to a source workspace. That kept old `run_dir` assumptions working, but it made relative path calculations, cleanup, state/audit projection, bundle generation, and upload materialization fragile. The same physical workspace could be addressed through multiple paths, which caused `relative_to` failures and made it unclear which path owned `.state`, `.audit`, and bundle files.

## Goals
- New request-bound runs do not create `data/runs/<run_id>` directories or symlinks.
- New physical workspaces live under `data/workspaces/<workspace_id>`.
- Reuse runs inherit the source request's persisted `workspace_id` and `workspace_dir`.
- Request-bound lifecycle code resolves the persisted workspace layout before falling back to legacy `data/runs/<run_id>`.
- Cleanup deletes a physical workspace only after the last run reference is gone.

## Non-Goals
- Migrate historical filesystem data.
- Rename every internal `run_dir` parameter in this change.
- Change public request ids or run ids.
