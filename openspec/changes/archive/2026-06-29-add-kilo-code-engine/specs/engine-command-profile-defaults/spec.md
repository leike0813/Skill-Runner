## ADDED Requirements

### Requirement: Kilo command defaults MUST be profile declared

Kilo command defaults SHALL be declared in the adapter profile and consumed through the shared command-default contract.

#### Scenario: Kilo profile defaults

- **WHEN** the runtime builds a Kilo API command with profile defaults enabled
- **THEN** the defaults MUST include `run --format json --auto`
- **AND** Kilo-specific defaults MUST NOT be hardcoded in shared command-default modules
