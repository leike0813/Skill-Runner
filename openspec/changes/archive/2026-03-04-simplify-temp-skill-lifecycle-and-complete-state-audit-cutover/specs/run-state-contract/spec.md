## ADDED Requirements

### Requirement: State Files Are `.state/*`

New runs MUST persist current state only under `.state/state.json` and `.state/dispatch.json`.

#### Scenario: Waiting payload
- WHEN a run enters `waiting_user` or `waiting_auth`
- THEN current waiting payload is embedded in `.state/state.json`
- AND no legacy pending file is written

### Requirement: Terminal Result Is Terminal-Only

`result/result.json` MUST contain only terminal statuses.

#### Scenario: Non-terminal run
- WHEN a run is `queued`, `running`, `waiting_user`, or `waiting_auth`
- THEN `result/result.json` is not used as the current-state source
- AND any terminal result endpoint MUST report that the terminal result is not ready
