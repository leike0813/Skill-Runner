## ADDED Requirements

### Requirement: Adapter profiles MUST declare structured-output governance strategy

Adapter profiles MUST declare structured-output behavior explicitly instead of relying on engine-name branching hidden inside command builders.

#### Scenario: profile declares structured-output strategy surface
- **WHEN** runtime loads an adapter profile
- **THEN** the profile MUST declare structured-output mode, CLI schema strategy, compatibility-schema strategy, prompt-contract strategy, and payload canonicalizer behavior
- **AND** profile validation MUST fail fast if those fields are malformed or contain invalid enum values

#### Scenario: profile gates schema CLI injection separately from command defaults
- **WHEN** an engine supports schema-constrained CLI execution
- **THEN** the profile MUST expose an explicit boolean gate for output-schema CLI injection
- **AND** disabling that gate MUST suppress schema CLI argument injection without changing the rest of the command defaults
