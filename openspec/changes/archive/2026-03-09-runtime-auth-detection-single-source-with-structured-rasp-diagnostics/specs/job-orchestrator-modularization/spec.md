## ADDED Requirements

### Requirement: lifecycle auth transition MUST consume auth_signal snapshot only
run lifecycle MUST consume execution-stage `auth_signal_snapshot` as its only auth classification source.

#### Scenario: high-confidence signal enters waiting_auth
- **GIVEN** `auth_signal_snapshot.required=true` and `confidence=high`
- **WHEN** run terminal normalization executes
- **THEN** lifecycle MUST enter `waiting_auth` path when session capability permits.

#### Scenario: low-confidence signal stays diagnostic-only
- **GIVEN** `auth_signal_snapshot.required=true` and `confidence=low`
- **WHEN** run terminal normalization executes
- **THEN** lifecycle MUST NOT transition to `waiting_auth` based solely on this signal.
