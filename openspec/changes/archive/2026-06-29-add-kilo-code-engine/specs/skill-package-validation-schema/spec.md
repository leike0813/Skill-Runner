## ADDED Requirements

### Requirement: Skill manifests MAY target kilo

Skill package validation SHALL allow Kilo engine-specific config declarations.

#### Scenario: runner manifest declares Kilo config

- **WHEN** a skill manifest declares an engine config for `kilo`
- **THEN** validation MUST accept the engine key
- **AND** runtime resolution MAY fall back to `assets/kilo_config.json`
