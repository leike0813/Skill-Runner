## MODIFIED Requirements

### Requirement: Final wrapper materialization MUST preserve object-union branch semantics

When a business output schema is an object schema containing `oneOf` or `anyOf`, runtime MUST preserve that union while adding the Skill Runner completion marker.

#### Scenario: Object-union output schema receives completion marker in every branch
- **GIVEN** a business output schema has root `type=object`
- **AND** it contains `oneOf` or `anyOf` object branches
- **WHEN** the final wrapper schema is materialized
- **THEN** the schema root requires `__SKILL_DONE__=true`
- **AND** each object branch also allows and requires `__SKILL_DONE__=true`
- **AND** branch schemas with `additionalProperties=false` can validate a final payload containing the marker

#### Scenario: Non-object schema keeps legacy result wrapper
- **GIVEN** a business output schema does not declare root `type=object`
- **WHEN** the final wrapper schema is materialized
- **THEN** runtime continues to wrap the business payload under `result`
