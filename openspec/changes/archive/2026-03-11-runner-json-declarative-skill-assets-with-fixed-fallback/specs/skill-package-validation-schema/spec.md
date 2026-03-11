## ADDED Requirements

### Requirement: runner.json asset declarations MAY fallback to canonical filenames
Skill packages MAY omit or misdeclare schema asset paths in `runner.json`, as long as canonical fallback filenames are present and resolvable within the skill root.

#### Scenario: schema declaration missing but fallback exists
- **GIVEN** `runner.json.schemas.output` is missing
- **AND** `assets/output.schema.json` exists
- **THEN** validation MUST accept the skill package

#### Scenario: schema declaration invalid and fallback exists
- **GIVEN** `runner.json.schemas.input` is empty, invalid, escapes the skill root, or points to a missing file
- **AND** `assets/input.schema.json` exists
- **THEN** validation MUST accept the skill package
- **AND** validation MUST emit a warning

#### Scenario: schema declaration unresolved and fallback missing
- **GIVEN** `runner.json.schemas.parameter` cannot be resolved
- **AND** `assets/parameter.schema.json` does not exist
- **THEN** validation MUST reject the skill package

### Requirement: runner.json MAY declare engine-specific config assets
Skill packages MAY declare engine-specific skill config files in `runner.json.engine_configs`.

#### Scenario: engine config declaration exists
- **GIVEN** `runner.json.engine_configs.gemini` points to a valid skill-local file
- **THEN** runtime MUST prefer that file over the fixed fallback filename
