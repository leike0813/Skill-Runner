# runtime-dispatch-state Specification

## Purpose
TBD - created by archiving change complete-runtime-file-contract-cutover-and-scan. Update Purpose after archive.
## Requirements
### Requirement: DB State And Dispatch Are The Only Current Runtime Truth

For request-bound runs, current runtime truth MUST come from DB state, projection, and dispatch rows.

#### Scenario: non-terminal state is rendered
- **WHEN** APIs, observability, or UI render a new run in `queued`, `running`, `waiting_auth`, or `waiting_user`
- **THEN** they read `request_run_state` and `request_current_projection`
- **AND** they read `request_dispatch_state` for dispatch phase details
- **AND** they do not fallback to `.state/*.json`, `status.json`, or `current/projection.json`

### Requirement: New Runs Must Not Read File Current Truth

File-based current-truth artifacts MUST NOT be used for request-bound runs.

#### Scenario: legacy files are missing for a new run
- **WHEN** a new run lacks `.state/*`, `status.json`, `current/projection.json`, and `interactions/*`
- **THEN** status and pending reads still succeed from DB rows
- **AND** no compatibility fallback is attempted


### Requirement: Dispatch state MUST be DB-backed for request-bound runs

Request-bound dispatch state MUST be stored and read from the `request_dispatch_state` DB table.

#### Scenario: Dispatch phase advances
- **WHEN** a request-bound dispatch phase advances
- **THEN** `request_dispatch_state` is updated in the run state DB
- **AND** the current projection is updated when the phase affects visible state
- **AND** no dispatch JSON file is required.

#### Scenario: Dispatch file is stale
- **GIVEN** `request_dispatch_state` has phase `attempt_materializing`
- **AND** `.state/<namespace>/dispatch.json` has phase `created`
- **WHEN** management or observability reads dispatch information
- **THEN** it uses the DB phase.
