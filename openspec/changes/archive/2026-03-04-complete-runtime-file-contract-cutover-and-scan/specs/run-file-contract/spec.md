## ADDED Requirements

### Requirement: New Runs Emit Only Canonical Runtime Files

New runs MUST emit only the canonical runtime file layout.

#### Scenario: create-run initializes canonical directories only
- **WHEN** a new run directory is created
- **THEN** it contains `.state/`, `.audit/`, `result/`, `artifacts/`, `bundle/`, and `uploads/`
- **AND** it does not contain `interactions/`, `logs/`, `raw/`, `status.json`, `current/projection.json`, or root `input.json`

### Requirement: Waiting Payload Lives Only In State

Current waiting payload MUST live only inside `.state/state.json`.

#### Scenario: run enters waiting_auth or waiting_user
- **WHEN** the run transitions into `waiting_auth` or `waiting_user`
- **THEN** current waiting data is embedded under `.state/state.json.pending`
- **AND** no `interactions/pending*.json` file exists

### Requirement: New Runs Must Not Emit Legacy Output Files

New runs MUST NOT emit legacy output or mirror files.

#### Scenario: process output is captured for a new run
- **WHEN** attempt logs are written
- **THEN** `.audit/stdout.<attempt>.log` and `.audit/stderr.<attempt>.log` are used
- **AND** `logs/stdout.txt`, `logs/stderr.txt`, and `raw/output.json` are absent
