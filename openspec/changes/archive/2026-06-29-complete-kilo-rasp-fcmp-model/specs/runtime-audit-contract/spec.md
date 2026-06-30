## ADDED Requirements

### Requirement: Interrupted terminal attempts MUST include failure evidence

Audit materialization SHALL include semantic failure evidence when attempt metadata says execution ended failed, canceled, or interrupted, even if the engine stream did not emit an error row.

#### Scenario: Interrupted attempt has empty engine output
- **WHEN** an attempt has no parser failure marker
- **AND** attempt completion state is `interrupted`
- **THEN** RASP MUST include an `agent.turn_failed` event with fatal terminal metadata

#### Scenario: Parser failure is not duplicated
- **WHEN** the parser already emits `agent.turn_failed`
- **THEN** protocol projection MUST NOT add a duplicate fallback failure marker
