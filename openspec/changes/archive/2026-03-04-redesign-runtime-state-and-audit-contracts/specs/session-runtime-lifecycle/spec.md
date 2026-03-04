## ADDED Requirements

### Requirement: Runtime Lifecycle Uses State Files As Current Truth

The runtime MUST treat `.state/state.json` as the only authoritative current-state file for non-terminal runs.

#### Scenario: waiting state is represented in state file only
- **WHEN** a run enters `waiting_user` or `waiting_auth`
- **THEN** the current waiting payload MUST be embedded in `.state/state.json.pending`
- **AND** `result/result.json` MUST NOT be written for that waiting transition

### Requirement: Queued Runs Have Durable Dispatch Truth

Any run in `queued` MUST have both current state and dispatch truth persisted.

#### Scenario: create run initializes queued state
- **WHEN** a run is created
- **THEN** `.state/state.json` MUST exist with `status=queued`
- **AND** `.state/dispatch.json` MUST exist with `phase=created`
