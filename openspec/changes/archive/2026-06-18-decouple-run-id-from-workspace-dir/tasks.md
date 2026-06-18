# Tasks

- [x] Add `SYSTEM.WORKSPACES_DIR`.
- [x] Allocate new physical workspaces under `data/workspaces/<workspace_id>`.
- [x] Stop creating `data/runs/<run_id>` symlinks for reuse runs.
- [x] Store and consume `workspace_id/workspace_dir/workspace_namespace` before dispatch.
- [x] Resolve lifecycle, auth, interaction, recovery, observability, and management reads layout-first.
- [x] Make target output schema and Codex compat relative paths workspace-root aware.
- [x] Cleanup workspaces by reference count and purge workspaces on clear/reset.
- [x] Update docs and focused tests.
- [x] Run targeted validation.
