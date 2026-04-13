## MODIFIED Requirements

### Requirement: repair protocol MUST expose explicit round semantics
The target engine-turn protocol MUST describe repair as attempt-internal rounds rather than an implicit retry side effect.

#### Scenario: engine turn stays on the same attempt during repair
- **WHEN** a turn enters output convergence
- **THEN** the protocol model MUST describe repair work as `internal_round`s inside the current attempt
- **AND** it MUST reserve orchestrator repair events that carry both `attempt_number` and `internal_round_index`

### Requirement: repair MUST NOT create competing executors
Engine adapters and parsers MAY contribute repaired candidates, but they MUST NOT become separate repair authorities.

#### Scenario: adapter repair is subordinate to orchestrator ownership
- **WHEN** an adapter or parser applies deterministic repair
- **THEN** the resulting candidate MUST be treated as input to the orchestrator convergence executor
- **AND** the protocol MUST NOT describe adapter-level repair as a parallel governance path
