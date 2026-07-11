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
## Requirements

### Requirement: CodeBuddy persistent config MUST be provider partitioned

The runtime MUST use a stable configuration directory per virtual provider and MUST use the same provider directory for start and resume. Static model lookup MUST NOT read either provider directory or execute the CodeBuddy CLI.

#### Scenario: Providers run concurrently
- **WHEN** domestic and global jobs execute
- **THEN** they use different persistent directories and cannot read each other's session state
### Requirement: CodeBuddy run configuration MUST be system owned

Each run MUST materialize CODEBUDDY.md, .codebuddy/settings.json, .codebuddy/mcp.json, and .codebuddy/skills, with settings that disable updates, hooks, untrusted frontmatter hooks, and automatic project MCP loading. The shared run-folder bootstrapper MUST be the sole owner of the run-local skill snapshot; the CodeBuddy config composer MUST preserve that existing snapshot instead of deleting or copying it again.

#### Scenario: A skill requests custom settings
- **WHEN** skill or runtime input attempts to override managed settings
- **THEN** the adapter ignores or rejects the override and writes the system-owned settings

#### Scenario: An attempt uses the canonical run-local skill snapshot
- **WHEN** the CodeBuddy config composer receives a skill whose source path is `.codebuddy/skills/<skill-id>`
- **THEN** it writes the managed configuration without deleting, replacing, or recopying the skill snapshot
### Requirement: CodeBuddy headless and TUI launches MUST share managed credential environment construction

Provider canonicalization, inherited managed-variable removal, credential-state validation, token/network injection, and provider-scoped configuration roots MUST have one engine-local implementation used by both execution modes.

#### Scenario: Host environment contains CodeBuddy variables
- **WHEN** either a headless attempt or inline TUI is prepared
- **THEN** all inherited managed CodeBuddy variables are removed before only the selected provider values are injected
### Requirement: CodeBuddy TUI settings MUST be session local and enforced

The profile-driven UI-shell config MUST write `.codebuddy/settings.json` in the isolated session directory. It MUST default to Plan, deny `*`, disable bypass and auto modes, keep subagents in Plan, and disable hooks, untrusted frontmatter hooks, automatic project MCP, updates, prompt suggestions, and memory.

#### Scenario: CodeBuddy TUI session configuration is composed
- **WHEN** a provider-qualified CodeBuddy UI-shell launch is accepted
- **THEN** the session-local settings contain the enforced restrictions and cannot be weakened by host configuration

