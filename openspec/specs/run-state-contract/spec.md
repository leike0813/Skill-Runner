# run-state-contract Specification

## Purpose
TBD - created by archiving change simplify-temp-skill-lifecycle-and-complete-state-audit-cutover. Update Purpose after archive.
## Requirements
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

