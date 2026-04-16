## ADDED Requirements

### Requirement: Compat payloads are canonicalized before repair governance

Compat-schema engine payloads MUST be converted back into runner canonical form before output convergence decides whether a payload is final, pending, invalid, or repairable.

#### Scenario: Codex compat final is already valid

- **GIVEN** a Codex compat payload for an interactive skill where `__SKILL_DONE__ = true`
- **AND** inactive compat-only fields are explicit `null`
- **WHEN** output convergence validates the payload
- **THEN** the payload is canonicalized into the runner final shape before schema validation
- **AND** the payload MUST NOT enter repair solely because compat-only inactive fields were present

### Requirement: Repair families preserve folded revision history

Superseded finals MUST remain available as folded revision history rather than disappearing from chat entirely.

#### Scenario: Superseded final becomes folded revision

- **GIVEN** a repair family with an emitted final that later receives `assistant.message.superseded`
- **WHEN** chat history is rendered
- **THEN** the old final is no longer the primary-visible winner
- **AND** the old final remains present as an inline folded revision

### Requirement: Repair generations do not swallow later assistant commentary

Assistant intermediate/process rows emitted after a supersede MUST start a new repair generation for that family.

#### Scenario: Post-supersede commentary stays visible

- **GIVEN** a family where an initial final has been superseded
- **WHEN** the assistant emits later intermediate commentary before the next final
- **THEN** that commentary is rendered in a new draft bubble generation
- **AND** it is not folded into the superseded final revision
