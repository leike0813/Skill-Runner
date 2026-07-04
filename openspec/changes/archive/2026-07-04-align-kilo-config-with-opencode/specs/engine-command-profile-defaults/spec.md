## MODIFIED Requirements

### Requirement: Kilo command defaults MUST be profile declared

Kilo command, workspace, config, and UI shell defaults SHALL be declared in the adapter profile and consumed through shared profile contracts.

#### Scenario: Kilo profile config assets

- **WHEN** runtime and UI shell managers resolve Kilo config assets
- **THEN** runtime config assets MUST point to Kilo config files
- **AND** UI shell config assets MUST point to Kilo config files
- **AND** profile targets MUST preserve `.kilo/kilo.jsonc`
