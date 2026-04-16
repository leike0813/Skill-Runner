# runtime-turn-failure-governance Specification

## ADDED Requirements

### Requirement: RASP MUST expose semantic turn failure as `agent.turn_failed`

The system MUST promote engine-native semantic turn-failure rows into canonical RASP `agent.turn_failed` events.

#### Scenario: engine parser detects semantic turn failure

- **WHEN** a runtime parser detects an engine-native `turn.failed` semantic row
- **THEN** the runtime protocol MUST emit `agent.turn_failed`
- **AND** the event MUST carry the semantic failure message
- **AND** the original raw stdout/stderr evidence MUST remain in audit output

#### Scenario: turn completion and turn failure are mutually exclusive

- **WHEN** a single turn is normalized into runtime events
- **THEN** the system MUST emit at most one of `agent.turn_complete` or `agent.turn_failed`

### Requirement: Generic engine error rows MUST be governed as diagnostics

The system MUST preserve generic engine error-like rows as raw evidence and additionally normalize them into structured diagnostics without treating them as lifecycle truth.

#### Scenario: generic engine error row appears

- **WHEN** runtime output contains a generic engine `type:"error"` row or `item.type:"error"` row
- **THEN** the raw row MUST still be emitted as `raw.stdout` or `raw.stderr`
- **AND** the system MUST emit `diagnostic.warning`
- **AND** the diagnostic payload MUST include a stable `code` and pattern metadata describing the error shape

### Requirement: Terminal failure summary MUST prefer semantic turn-failure message

The system MUST prefer semantic turn-failure messages over generic process-exit summaries when producing terminal failure text.

#### Scenario: non-zero exit includes semantic turn-failure evidence

- **WHEN** the run exits non-zero and parser normalization captured a semantic turn-failure message
- **THEN** terminal projection and persisted result error text MUST use that semantic message
- **AND** user-facing failure chat replay MUST prefer that message over `Exit code N`
