## ADDED Requirements

### Requirement: Kilo config assets MUST reuse OpenCode-compatible semantics without OpenCode identity
Kilo runtime config assets SHALL use OpenCode-compatible config fields only where Kilo's upstream config schema accepts them, while preserving Kilo-specific file identity and defaults.

#### Scenario: Kilo config assets are validated
- **WHEN** Kilo bootstrap, default, enforced, and UI shell config layers are loaded
- **THEN** they MUST validate against the Kilo config schema
- **AND** `$schema` MUST reference `https://app.kilo.ai/config.json` when present
- **AND** the default model MUST NOT be an OpenCode model id

#### Scenario: Kilo enforced layer is composed
- **WHEN** Kilo runtime config layers are composed
- **THEN** provider timeout and permission rules MAY mirror OpenCode-compatible semantics
- **AND** governed MCP MUST remain the only source for final `mcp` root entries
- **AND** the final config target MUST remain `.kilo/kilo.jsonc`
