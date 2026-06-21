# reused-workspace-skill-runs Specification

## Purpose
TBD - created by archiving change support-reused-workspace-skill-runs. Update Purpose after archive.
## Requirements
### Requirement: Requests MAY reuse a completed request workspace
The system SHALL allow a new job request to reuse the physical workspace associated with a previous successful request.

#### Scenario: Reuse completed request workspace
- **GIVEN** request A has a successful terminal run with an existing workspace
- **WHEN** request B is created with `runtime_options.workspace.mode="reuse"` and `runtime_options.workspace.request_id` equal to request A
- **THEN** request B uses the same physical workspace as request A
- **AND** request B receives its own logical `run_id`

#### Scenario: Reject invalid reuse source
- **WHEN** a request is created with `runtime_options.workspace.mode="reuse"` and the source request is missing, active, failed, canceled, unbound, or has no workspace
- **THEN** the system rejects the request
- **AND** no new run is scheduled

### Requirement: Reused workspaces MUST isolate runner-owned files by namespace
The system SHALL allocate a provider-owned namespace for every logical run created in a workspace.

#### Scenario: Different skills use distinct namespaces
- **GIVEN** requests for `prepare-skill`, `core-skill`, and `finalize-skill` reuse one workspace in sequence
- **WHEN** each request starts execution
- **THEN** their runner-owned result and input-manifest paths are distinct
- **AND** earlier runner-owned files remain readable after later requests complete

#### Scenario: Repeated skill increments namespace
- **GIVEN** a workspace already contains a run namespace for `core-skill`
- **WHEN** another new request for `core-skill` reuses the same workspace
- **THEN** the new request uses the next 1-based namespace index for `core-skill`

### Requirement: Workspace reuse cache MUST include upstream lineage
The system SHALL include the reused source request's workspace output token in the downstream cache key.

#### Scenario: Different upstream output prevents downstream cache hit
- **GIVEN** request B reuses request A's workspace
- **AND** request A2 has different effective input from request A
- **WHEN** request B2 reuses request A2's workspace with otherwise identical B inputs
- **THEN** request B2 does not use request B's cached run

#### Scenario: Cached upstream enables downstream cache hit
- **GIVEN** request A3 uses the same effective inputs as request A and hits request A's cache
- **WHEN** request B3 reuses request A3's workspace with the same effective inputs as request B
- **THEN** request B3 may use request B's cached run

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

