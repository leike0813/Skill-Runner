## MODIFIED Requirements

### Requirement: AutoSkill required files must be present for temporary skills
The system MUST require temporary skill packages to include `SKILL.md`, `assets/runner.json`, and a resolvable `output` schema. `input` and `parameter` schemas are optional and are validated only when present.

#### Scenario: Reject missing required file
- **WHEN** a temporary skill package is missing `SKILL.md`, `assets/runner.json`, or a resolvable `output` schema
- **THEN** the system rejects the request as invalid

#### Scenario: Accept absent optional schemas
- **WHEN** a temporary skill package omits `input` or `parameter` schema assets
- **THEN** the system accepts the package when all other validation requirements pass
