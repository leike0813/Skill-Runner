## ADDED Requirements

### Requirement: FCMP terminal state MUST follow orchestrator terminal metadata

FCMP terminal state SHALL be derived from orchestrator status and completion metadata, while RASP preserves semantic evidence from both engine stream parsing and terminal fallback.

#### Scenario: Canceled attempt also has engine turn-complete evidence
- **WHEN** the engine stream contains a turn complete marker
- **AND** the attempt status is `canceled` or completion state is `interrupted`
- **THEN** RASP MAY retain the engine turn complete marker
- **AND** RASP MUST include terminal failure evidence
- **AND** FCMP terminal state MUST follow the orchestrator terminal status/completion
