## ADDED Requirements

### Requirement: Reused workspaces MUST support same-workspace file handoff
When a request reuses a workspace, the backend MUST support materializing files from another succeeded request in the same physical workspace into the current run uploads directory via `runtime_options.workspace.file_bindings`.

#### Scenario: source request is in the same workspace
- **WHEN** the source request is succeeded
- **AND** its physical `workspace_dir` equals the reuse source workspace directory
- **THEN** the backend may read `source_path` from that workspace for binding materialization

#### Scenario: source request is outside the reuse workspace
- **WHEN** the binding `source_request_id` resolves to a different physical `workspace_dir`
- **THEN** the backend rejects the request with a 4xx response

### Requirement: Workspace file bindings MUST materialize before cache manifest calculation
The backend MUST materialize workspace file bindings into staging uploads before computing input manifest and cache key.

#### Scenario: bound file changes cache identity
- **WHEN** two otherwise identical requests bind different source file contents to the same target path
- **THEN** their input manifest hashes differ
- **AND** the cache key MUST NOT incorrectly match due to omitted bound file content
