## MODIFIED Requirements

### Requirement: Harness MUST use the shared Claude resume contract

Harness resume for `claude` MUST align with the shared adapter resume command contract instead of maintaining a legacy Claude-specific expectation.

#### Scenario: Claude resume uses --resume session syntax

- **WHEN** harness resumes a Claude session through the shared adapter path
- **THEN** the generated command MUST include `--resume <session-id>`
- **AND** harness regression tests MUST assert the same observable command shape
