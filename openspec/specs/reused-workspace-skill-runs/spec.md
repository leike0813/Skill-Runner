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

