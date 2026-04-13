## MODIFIED Requirements

### Requirement: interactive lifecycle MUST distinguish attempt lifecycle from internal repair rounds
The target interactive lifecycle MUST treat repair rounds as attempt-internal convergence, not as lifecycle-level retries.

#### Scenario: repair rounds do not mutate attempt ownership
- **WHEN** an interactive turn enters output convergence
- **THEN** any repair rounds MUST remain inside the active attempt
- **AND** `attempt_number` ownership MUST remain unchanged until the lifecycle leaves that attempt

### Requirement: legacy waiting and completion semantics MUST be modeled as fallback stages
The current interactive waiting/completion heuristics MUST be documented as legacy fallbacks inside the unified convergence pipeline.

#### Scenario: ask-user evidence remains a legacy waiting fallback
- **WHEN** current runtime behavior derives `waiting_user` from `<ASK_USER_YAML>` or equivalent ask-user evidence
- **THEN** the spec MUST describe that path as `legacy / current implementation only`
- **AND** it MUST NOT be described as the target repair-owned waiting source

#### Scenario: soft completion remains a legacy completion fallback
- **WHEN** current runtime behavior completes an interactive turn without an explicit done marker
- **THEN** the spec MUST describe that path as `legacy / current implementation only`
- **AND** it MUST NOT be described as the target convergence contract
