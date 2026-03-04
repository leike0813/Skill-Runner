## ADDED Requirements

### Requirement: Orchestration MUST publish live FCMP state transitions through a shared publisher
The system MUST route orchestration-originated FCMP events through the same live publisher used by parser-originated FCMP events so that active delivery observes a single canonical timeline.

#### Scenario: orchestration state change is visible before audit mirror
- **WHEN** orchestration transitions a run between canonical conversation states
- **THEN** it MUST publish the corresponding FCMP event to the live publisher immediately
- **AND** audit mirroring MAY occur asynchronously afterward

### Requirement: Audit mirrors MUST NOT serve as current truth for active delivery
The system MUST treat audit FCMP/RASP files as history mirrors and MUST NOT require them to exist before active delivery can proceed.

#### Scenario: active delivery ignores audit mirror latency
- **WHEN** a published FCMP or RASP event has not yet been mirrored to disk
- **THEN** SSE and recent history replay MUST still be able to serve the event from live memory
