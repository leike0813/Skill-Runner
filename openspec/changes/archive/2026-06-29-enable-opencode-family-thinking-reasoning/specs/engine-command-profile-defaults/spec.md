## MODIFIED Requirements

### Requirement: Kilo command defaults MUST be profile declared

Kilo command defaults SHALL be declared in the adapter profile and consumed through the shared command-default contract.

#### Scenario: Kilo profile defaults

- **WHEN** the runtime builds a Kilo API command with profile defaults enabled
- **THEN** the defaults MUST include `run --format json --auto --thinking`
- **AND** Kilo-specific defaults MUST NOT be hardcoded in shared command-default modules

## ADDED Requirements

### Requirement: OpenCode-family command defaults MUST enable thinking

OpenCode-family engines that support a thinking flag SHALL enable it through adapter profile command defaults.

#### Scenario: OpenCode profile defaults

- **WHEN** the runtime builds an OpenCode API command with profile defaults enabled
- **THEN** the defaults MUST include `--format json --thinking`
- **AND** OpenCode-specific defaults MUST NOT be hardcoded in shared command-default modules

#### Scenario: Kilo resume profile defaults

- **WHEN** the runtime builds a Kilo resume command with profile defaults enabled
- **THEN** the defaults MUST include `run --format json --auto --thinking --session`
- **AND** the session id MUST still be appended as the value for `--session`
