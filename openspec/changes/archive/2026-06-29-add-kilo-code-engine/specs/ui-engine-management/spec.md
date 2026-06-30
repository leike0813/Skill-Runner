## ADDED Requirements

### Requirement: UI engine list MUST include Kilo

The engine management UI SHALL display Kilo Code as an available engine.

#### Scenario: Display Kilo in engine list

- **WHEN** the user opens the engine management page
- **THEN** the UI MUST show `Kilo Code` with identifier `kilo`
- **AND** it MUST display installation and version status when available

### Requirement: Kilo phase 1 MUST not expose auth actions

Kilo phase 1 SHALL not expose interactive auth or provider-aware auth actions.

#### Scenario: Kilo auth controls are hidden

- **WHEN** the UI renders the Kilo engine card
- **THEN** it MUST NOT show Kilo auth provider or credential import actions
