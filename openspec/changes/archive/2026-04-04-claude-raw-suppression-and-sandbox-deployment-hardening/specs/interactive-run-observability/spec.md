## MODIFIED Requirements

### Requirement: Raw Output Is Supplemental Evidence

Runtime raw output SHOULD act as supplemental evidence after semantic parsing, not as the dominant output channel when semantic events are already available.

#### Scenario: Claude semantic rows suppress duplicate raw stdout
- **WHEN** Claude emits semantic runtime events with valid `raw_ref`
- **THEN** duplicate `raw.stdout` emission SHOULD be suppressed for the same byte range
- **AND** observability consumers SHOULD still retain `raw_ref` jump targets through semantic events

### Requirement: Sandbox Degradation Is Visible

Interactive run observability MUST surface sandbox degradation or failure as diagnostics.

#### Scenario: Claude sandbox runtime failure
- **WHEN** Claude output contains known sandbox failure signals
- **THEN** the run observability stream MUST include a stable warning diagnostic
- **AND** the terminal run outcome MUST continue to reflect the actual command result
