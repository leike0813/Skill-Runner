## MODIFIED Requirements

### Requirement: Output schema validation MUST keep root object strictness while allowing object unions

Skill package output schema validation MUST continue to require a root object schema, and MUST allow object schemas that express their business result as `oneOf` or `anyOf` branches.

#### Scenario: Root object union passes output schema validation
- **GIVEN** `output.schema.json` declares `type=object`
- **AND** it contains valid `oneOf` or `anyOf` object branches
- **WHEN** the skill package is validated
- **THEN** output schema validation passes

#### Scenario: Pure top-level union remains invalid
- **GIVEN** `output.schema.json` contains top-level `oneOf` or `anyOf`
- **AND** it does not declare root `type=object`
- **WHEN** the skill package is validated
- **THEN** output schema validation fails
