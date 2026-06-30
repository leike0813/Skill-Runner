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
