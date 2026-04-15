## ADDED Requirements

### Requirement: Interactive Lifecycle Uses Explicit Branch Priority First

Interactive lifecycle normalization MUST treat explicit final and pending
branches as the primary contract before any compatibility fallback.

#### Scenario: final branch outranks all compatibility paths
- **WHEN** an interactive attempt resolves a valid final branch
- **THEN** runtime MUST evaluate that branch before pending, soft completion, or
  waiting fallback

#### Scenario: pending branch outranks soft completion and waiting fallback
- **WHEN** an interactive attempt resolves a valid pending branch
- **THEN** runtime MUST enter `waiting_user`
- **AND** it MUST NOT continue into soft completion or generic waiting fallback

### Requirement: Compatibility Paths Remain Secondary

Phase 5 MUST keep compatibility completion and waiting paths, but only after the
explicit branches fail to resolve.

#### Scenario: soft completion remains available after branch miss
- **WHEN** an interactive attempt does not resolve a valid final or pending
  branch
- **AND** structured business output remains schema-valid
- **THEN** runtime MAY succeed via soft completion

#### Scenario: waiting fallback remains the last compatibility path
- **WHEN** an interactive attempt resolves neither a valid final nor pending
  branch
- **AND** soft completion does not apply
- **THEN** runtime MAY still enter `waiting_user`
- **AND** it MUST use the default fallback pending payload
