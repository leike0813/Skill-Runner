# runtime-event-command-schema Specification Delta

## ADDED Requirements

### Requirement: auth payload MUST expose phase and timeout metadata
Auth-related FCMP payloads MUST expose phase metadata and timeout metadata.

#### Scenario: backend emits auth-related FCMP payload
- **GIVEN** the system emits auth-related FCMP payload
- **WHEN** payload is consumed by UI or API clients
- **THEN** payload MUST include `phase`
- **AND** payload SHOULD include `available_methods`, `selected_method`, `timeout_sec`, and `expires_at`

### Requirement: pending auth payload MUST support callback URL input kind
Pending auth challenge payload MUST support callback URL input kind.

#### Scenario: backend emits pending auth challenge
- **GIVEN** the system emits pending auth challenge payload
- **WHEN** challenge kind or input kind is validated
- **THEN** it MUST support `callback_url`
