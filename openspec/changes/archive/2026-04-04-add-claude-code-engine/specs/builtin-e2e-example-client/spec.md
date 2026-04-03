## MODIFIED Requirements

### Requirement: E2E run form supports Claude

The built-in E2E example client SHALL allow runs to target `claude`.

#### Scenario: Render E2E run form

- **WHEN** the E2E client loads engine options
- **THEN** `claude` MUST be selectable
- **AND** its models MUST come from the management engine detail / manifest-backed catalog
