## ADDED Requirements

### Requirement: State And Dispatch Are The Only Current Runtime Truth

For new runs, current runtime truth MUST come from `.state/state.json` and `.state/dispatch.json`.

#### Scenario: non-terminal state is rendered
- **WHEN** APIs, observability, or UI render a new run in `queued`, `running`, `waiting_auth`, or `waiting_user`
- **THEN** they read `.state/state.json` first
- **AND** they read `.state/dispatch.json` for dispatch phase details
- **AND** they do not fallback to `status.json` or `current/projection.json`

### Requirement: New Runs Must Not Read Legacy Current Truth

Legacy current-truth files MUST NOT be used for new runs.

#### Scenario: legacy files are missing for a new run
- **WHEN** a new run lacks `status.json`, `current/projection.json`, and `interactions/*`
- **THEN** status and pending reads still succeed from `.state/*`
- **AND** no compatibility fallback is attempted
