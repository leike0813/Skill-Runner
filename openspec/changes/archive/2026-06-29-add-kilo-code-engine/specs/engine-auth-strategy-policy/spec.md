## ADDED Requirements

### Requirement: Kilo auth strategy MAY declare phase-1 disabled auth

The shared auth strategy contract SHALL allow Kilo to be present without exposing a startable auth session in phase 1.

#### Scenario: Kilo auth strategy loads

- **WHEN** the auth strategy service loads all active engines
- **THEN** Kilo strategy config MUST validate
- **AND** Kilo MUST NOT register provider-aware auth providers
- **AND** Kilo MUST NOT expose startable auth transports in UI capability output
