## ADDED Requirements

### Requirement: Skill manifests MAY target kilo

Skill package validation SHALL allow Kilo engine-specific config declarations.

#### Scenario: runner manifest declares Kilo config

- **WHEN** a skill manifest declares an engine config for `kilo`
- **THEN** validation MUST accept the engine key
- **AND** runtime resolution MAY fall back to `assets/kilo_config.json`
## Requirements

### Requirement: Skill manifests MAY target codebuddy

The skill manifest schema MUST accept codebuddy in supported and unsupported engine declarations and runtime validation MUST use the same active-engine vocabulary.

#### Scenario: Skill explicitly supports CodeBuddy
- **WHEN** a manifest contains engines with codebuddy
- **THEN** schema validation succeeds and the skill can be selected for a CodeBuddy job

