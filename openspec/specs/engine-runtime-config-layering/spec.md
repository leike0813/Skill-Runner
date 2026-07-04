## ADDED Requirements

### Requirement: OpenCode bootstrap config MUST NOT enable Google AntiGravity
OpenCode bootstrap config SHALL NOT install or configure Google AntiGravity defaults.

#### Scenario: Bootstrap config is composed
- **WHEN** OpenCode runtime config layers are composed
- **THEN** the bootstrap layer MUST NOT include `opencode-antigravity-auth@latest`
- **AND** it MUST NOT include `provider.google`

### Requirement: Qwen defaults MUST NOT select qwen-oauth
Qwen default runtime config SHALL not select the discontinued OAuth auth type.

#### Scenario: Qwen default config is composed
- **WHEN** Qwen runtime config layers are composed
- **THEN** `security.auth.selectedType` MUST NOT be `qwen-oauth`

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
