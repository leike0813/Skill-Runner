## ADDED Requirements

### Requirement: State Files Are Canonical And Consolidated

Runtime current state MUST be consolidated under `.state/`.

#### Scenario: pending payload is embedded in state
- **WHEN** the run has a current waiting owner
- **THEN** `.state/state.json.pending.owner` MUST identify the waiting owner
- **AND** `.state/state.json.pending.payload` MUST carry the current waiting payload

### Requirement: Terminal Result Is Terminal Only

`result/result.json` MUST only represent terminal truth.

#### Scenario: non-terminal result is rejected
- **WHEN** the run status is `queued`, `running`, `waiting_user`, or `waiting_auth`
- **THEN** `result/result.json` MUST NOT be used as canonical current state
