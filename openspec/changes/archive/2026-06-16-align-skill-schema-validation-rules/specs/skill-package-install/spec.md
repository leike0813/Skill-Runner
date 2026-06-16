## MODIFIED Requirements

### Requirement: Enforce AutoSkill Profile validation
The system MUST validate the uploaded skill package against the Runner AutoSkill Profile before installation. The package MUST include `SKILL.md`, `assets/runner.json`, and a resolvable `output` schema. `input` and `parameter` schemas are optional.

#### Scenario: Missing required structural files
- **WHEN** the package is missing any required structural file (`SKILL.md`, `assets/runner.json`)
- **THEN** the system rejects the package as invalid

#### Scenario: Optional schema assets are absent
- **WHEN** `input` or `parameter` schema assets are not resolvable from `runner.json.schemas` or canonical fallback files
- **THEN** the system accepts the package

#### Scenario: Required output schema missing
- **WHEN** the `output` schema asset cannot be resolved from `runner.json.schemas.output` or `assets/output.schema.json`
- **THEN** the system rejects the package as invalid
