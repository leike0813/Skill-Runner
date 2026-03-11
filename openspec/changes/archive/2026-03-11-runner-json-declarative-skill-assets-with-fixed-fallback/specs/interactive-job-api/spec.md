## ADDED Requirements

### Requirement: skill asset reads MUST follow the shared declaration-plus-fallback resolver
Runtime schema validation, artifact inference, and management schema reads MUST use the same skill asset resolution behavior.

#### Scenario: management schema read follows fallback
- **GIVEN** `runner.json.schemas.output` is missing
- **AND** `assets/output.schema.json` exists
- **THEN** management schema inspection MUST read the fallback file successfully
