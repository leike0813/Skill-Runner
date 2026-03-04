# run-current-projection Specification Delta

## ADDED Requirements

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
- **AND** only `interactions/pending.json` may exist as current pending payload

#### Scenario: auth method selection is active
- **GIVEN** the current projection is `waiting_auth` with auth method selection
- **THEN** `pending_owner` MUST be `waiting_auth.method_selection`
- **AND** only `interactions/pending_auth_method_selection.json` may exist as current pending payload

#### Scenario: auth challenge is active
- **GIVEN** the current projection is `waiting_auth` with an active auth challenge
- **THEN** `pending_owner` MUST be `waiting_auth.challenge_active`
- **AND** only `interactions/pending_auth.json` may exist as current pending payload

### Requirement: terminal result MUST be terminal-only
The backend MUST treat `result/result.json` as a terminal artifact, not as a current-state snapshot.

#### Scenario: run is non-terminal
- **GIVEN** a run is in `queued`, `running`, `waiting_user`, or `waiting_auth`
- **WHEN** the backend persists current state
- **THEN** it MUST NOT write a non-terminal envelope to `result/result.json`

#### Scenario: run reaches terminal state
- **GIVEN** a run reaches `succeeded`, `failed`, or `canceled`
- **WHEN** terminal artifacts are written
- **THEN** `result/result.json` MUST contain terminal truth only
- **AND** current pending owner MUST be empty

