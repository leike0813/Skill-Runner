## ADDED Requirements

### Requirement: interactive waiting_auth trigger MUST be high-confidence only
Interactive run auth gating MUST only treat `auth_signal.confidence=high` as waiting-auth trigger input.

#### Scenario: low-confidence signal does not change waiting_auth semantics
- **GIVEN** interactive run has `auth_signal.required=true` with `confidence=low`
- **WHEN** backend evaluates terminal mapping for interactive run
- **THEN** backend MUST keep the signal as diagnostic-only and MUST NOT transition to `waiting_auth` from it.
