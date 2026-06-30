## ADDED Requirements

### Requirement: Kilo runtime config MUST use project-level `.kilo/kilo.jsonc`

Kilo runtime configuration SHALL be written to `<workspace_root>/.kilo/kilo.jsonc`.

#### Scenario: Compose Kilo run config

- **WHEN** a Kilo run is prepared
- **THEN** the runtime MUST create `.kilo/`
- **AND** it MUST write JSON-compatible content to `.kilo/kilo.jsonc`

### Requirement: Kilo MUST use shared non-Codex config layering

Kilo config composition SHALL follow the shared layering order used by other JSON-configured engines.

#### Scenario: Merge Kilo config layers

- **WHEN** Kilo config is composed
- **THEN** layers MUST be applied as `engine_default -> skill defaults -> runtime kilo_config -> model overlay -> governed MCP -> enforced`

### Requirement: Kilo phase 1 MUST reject user-authored provider roots

Kilo phase 1 SHALL not implement third-party provider config.

#### Scenario: Runtime override contains provider root

- **WHEN** `kilo_config` contains a top-level `provider`
- **THEN** runtime config preparation MUST reject the run before engine launch

#### Scenario: Skill config contains provider root

- **WHEN** a Kilo skill config asset contains a top-level `provider`
- **THEN** runtime config preparation MUST reject the run before engine launch
