## ADDED Requirements

### Requirement: Interactive Waiting Uses Pending JSON As The Primary Source

Interactive runs MUST treat a valid pending JSON branch as the primary source of
`waiting_user`.

#### Scenario: Valid pending JSON projects directly into waiting_user
- **WHEN** an interactive attempt resolves the pending branch of the union schema
- **THEN** runtime MUST project that branch into canonical `PendingInteraction`
- **AND** the run MUST enter `waiting_user` without legacy enrichment

### Requirement: Legacy Waiting Fallback Is Generic

Legacy fallback MAY still produce `waiting_user`, but it MUST no longer derive
rich pending fields from deprecated output forms.

#### Scenario: Legacy fallback uses the default pending payload
- **WHEN** an interactive attempt does not converge to a valid pending/final
  branch and lifecycle still falls back to waiting
- **THEN** runtime MUST synthesize a default pending payload
- **AND** it MUST NOT recover prompt, kind, options, or hints from YAML wrappers,
  runtime-stream text, or direct interaction-like payloads
