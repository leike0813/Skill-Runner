# run-current-projection Specification

## Purpose
TBD - created by archiving change stabilize-runtime-resume-idempotency-and-attempt-ownership. Update Purpose after archive.
## Requirements
### Requirement: current projection MUST be the single source of truth for non-terminal state
The backend MUST persist a current projection for each run and use it as the canonical current-state read model.

#### Scenario: a run is queued, running, or waiting
- **GIVEN** a run is in `queued`, `running`, `waiting_user`, or `waiting_auth`
- **WHEN** the backend exposes current status to API, UI, or observability consumers
- **THEN** it MUST read current truth from current projection
- **AND** it MUST NOT infer current truth from stale terminal result payloads

### Requirement: pending owner MUST match current status
The backend MUST keep current pending ownership aligned with the current status.

#### Scenario: waiting owner is active
- **GIVEN** the current projection is `waiting_user`
- **THEN** `pending_owner` MUST be `waiting_user`
- **AND** the pending payload MUST be read from DB interaction rows

#### Scenario: auth method selection is active
- **GIVEN** the current projection is `waiting_auth` with auth method selection
- **THEN** `pending_owner` MUST be `waiting_auth.method_selection`
- **AND** the pending payload MUST be read from DB auth method-selection rows

#### Scenario: auth challenge is active
- **GIVEN** the current projection is `waiting_auth` with an active auth challenge
- **THEN** `pending_owner` MUST be `waiting_auth.challenge_active`
- **AND** the pending payload MUST be read from DB auth challenge rows

### Requirement: terminal result MUST be terminal-only
The backend MUST treat the persisted `resultJsonPath` as a terminal artifact, not as a current-state snapshot.

#### Scenario: run is non-terminal
- **GIVEN** a run is in `queued`, `running`, `waiting_user`, or `waiting_auth`
- **WHEN** the backend persists current state
- **THEN** it MUST NOT write a non-terminal envelope to `result/<namespace>/result.json`

#### Scenario: run reaches terminal state
- **GIVEN** a run reaches `succeeded`, `failed`, or `canceled`
- **WHEN** terminal artifacts are written
- **THEN** `result/<namespace>/result.json` MUST contain terminal truth only
- **AND** current pending owner MUST be empty

### Requirement: Run projections MUST expose workspace diagnostics
Run status and management projections SHALL expose physical workspace and actual runner-owned path diagnostics.

#### Scenario: Status includes workspace diagnostics
- **WHEN** a client reads a request status or management run detail
- **THEN** the response includes `workspaceDir`, `resultJsonPath`, and `inputManifestPath` when known

#### Scenario: Diagnostics follow cached run binding
- **WHEN** a request is served from cache
- **THEN** its status diagnostics reference the cached run's actual workspace/result/input-manifest paths

### Requirement: Current projection reads MUST distinguish missing request from pre-observable request
The current-state read model MUST distinguish an unknown `request_id` from a known request that does not yet have an observable run.

#### Scenario: Pre-observable request has no current projection yet
- **GIVEN** a request record exists
- **AND** no current projection exists because no run has been bound
- **WHEN** the status API is read
- **THEN** the response MUST be a queued request projection
- **AND** it MUST expose `observability_ready=false`

#### Scenario: Bound run remains observable
- **GIVEN** a request record has a bound and resolvable run
- **WHEN** the status API is read
- **THEN** the response MUST expose `observability_ready=true`


### Requirement: Read projections MUST resolve workspace layout first

Status, list, detail, logs, events, chat, and management projections MUST require persisted workspace layout for bound request records.

#### Scenario: Run list and detail read physical workspace
- **GIVEN** a request record has `workspace_dir`
- **WHEN** list or detail projections read current state
- **THEN** they read DB state/projection rows
- **AND** they do not require `data/runs/<run_id>` to exist.

#### Scenario: Logs read namespaced audit under workspace
- **GIVEN** a request record has `workspace_dir` and `workspace_namespace`
- **WHEN** log tail or log range is requested
- **THEN** stdout/stderr are read from `.audit/<namespace>/`
- **AND** legacy root `.audit/stdout.*.log` is not read.

### Requirement: Current run state MUST come from DB projection/state

Request-bound status, list, detail, reply gating, cancel gating, and management projections MUST use DB state/projection rows as the current truth.

#### Scenario: State file disagrees with DB state
- **GIVEN** a request-bound run has DB state `succeeded`
- **AND** `.state/<namespace>/state.json` exists with status `running`
- **WHEN** status, list, detail, reply, or cancel reads current state
- **THEN** the response uses `succeeded`
- **AND** the file payload is ignored for state decisions.

#### Scenario: Request-bound state files are absent
- **GIVEN** a request-bound run has DB state and dispatch rows
- **WHEN** observability reads status or detail
- **THEN** it succeeds without `.state/<namespace>/state.json`
- **AND** it succeeds without `.state/<namespace>/dispatch.json`.
