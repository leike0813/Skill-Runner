## MODIFIED Requirements

### Requirement: Kilo phase 1 MUST reject user-authored provider roots
Kilo phase 2 SHALL allow user-authored top-level `provider` roots in skill and runtime Kilo config layers while continuing to reject user-authored top-level `mcp` roots.

#### Scenario: Runtime override contains provider root

- **WHEN** `kilo_config` contains a top-level `provider`
- **THEN** runtime config preparation MUST include the provider config in `.kilo/kilo.jsonc`

#### Scenario: Skill config contains provider root

- **WHEN** a Kilo skill config asset contains a top-level `provider`
- **THEN** runtime config preparation MUST include the provider config in `.kilo/kilo.jsonc`

#### Scenario: Runtime override contains mcp root

- **WHEN** `kilo_config` contains a top-level `mcp`
- **THEN** runtime config preparation MUST reject the run before engine launch
