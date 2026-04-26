## ADDED Requirements

### Requirement: System MCP registry MUST be the source of truth
The system SHALL define MCP servers in a system-owned registry file validated by a machine-readable schema. Skills SHALL NOT define MCP server commands, URLs, headers, environment variables, or secrets inline.

#### Scenario: Registry entry is loaded from system config
- **WHEN** the runtime initializes MCP governance
- **THEN** it MUST load MCP server definitions from the system registry
- **AND** it MUST validate the registry against the MCP registry schema

#### Scenario: Skill attempts inline MCP definition
- **WHEN** a skill manifest contains inline MCP command, URL, env, header, or secret configuration
- **THEN** the manifest or run validation MUST reject the skill configuration

### Requirement: MCP activation classes MUST control enablement
Each registry entry MUST declare `activation` as either `default` or `declared`. `default` entries SHALL be enabled automatically for matching engines. `declared` entries SHALL be enabled only when the skill references the entry ID in `runner.json.mcp.required_servers`.

#### Scenario: Default MCP matches current engine
- **GIVEN** a registry entry has `activation="default"`
- **AND** the current run engine is included in the entry effective engines
- **WHEN** runtime resolves MCP servers for the run
- **THEN** the entry MUST be included without a skill declaration

#### Scenario: Declared MCP is not requested
- **GIVEN** a registry entry has `activation="declared"`
- **AND** the current skill does not include its ID in `runner.json.mcp.required_servers`
- **WHEN** runtime resolves MCP servers for the run
- **THEN** the entry MUST NOT be included

#### Scenario: Declared MCP is requested
- **GIVEN** a registry entry has `activation="declared"`
- **AND** the current skill includes its ID in `runner.json.mcp.required_servers`
- **AND** the current run engine is included in the entry effective engines
- **WHEN** runtime resolves MCP servers for the run
- **THEN** the entry MUST be included for that run

### Requirement: MCP registry entries MUST support engine filtering
Registry entries SHALL support optional `engines` and `unsupported_engines` fields. Omitted `engines` SHALL mean all supported engines. The effective engines MUST be computed as `(engines if provided else all_supported) - unsupported_engines`, and the result MUST be non-empty.

#### Scenario: Default MCP only applies to selected engines
- **GIVEN** a default MCP entry declares `engines=["codex"]`
- **WHEN** a run uses `codex`
- **THEN** the entry MUST be enabled by default
- **WHEN** a run uses `gemini`
- **THEN** the entry MUST NOT be enabled by default

#### Scenario: Declared MCP does not support current engine
- **GIVEN** a declared MCP entry does not include the current run engine in its effective engines
- **AND** the skill references that entry ID
- **WHEN** runtime validates MCP requirements
- **THEN** the run MUST be rejected before engine launch

### Requirement: MCP registry MUST reject unsupported secret-bearing fields
The first MCP governance version SHALL reject registry entries that include environment variables, headers, bearer-token references, credential references, or other secret-bearing fields.

#### Scenario: Registry entry contains headers
- **WHEN** the MCP registry contains a server entry with `headers`
- **THEN** registry validation MUST fail

#### Scenario: Registry entry contains env
- **WHEN** the MCP registry contains a server entry with `env`
- **THEN** registry validation MUST fail

### Requirement: MCP renderer MUST emit engine-native config roots
The system SHALL render resolved MCP entries into the target engine's native configuration shape.

#### Scenario: Codex MCP rendering
- **WHEN** the runtime renders MCP entries for `codex`
- **THEN** output MUST use the `mcp_servers` root

#### Scenario: JSON MCP rendering
- **WHEN** the runtime renders MCP entries for `gemini`, `qwen`, or `claude`
- **THEN** output MUST use the `mcpServers` root

#### Scenario: OpenCode MCP rendering
- **WHEN** the runtime renders MCP entries for `opencode`
- **THEN** output MUST use the `mcp` root

### Requirement: Declared MCP MUST remain run-local
Declared MCP entries SHALL NOT be written to a long-lived shared engine configuration. They MUST affect only the run whose skill requested them.

#### Scenario: Declared MCP is resolved
- **GIVEN** a declared MCP entry is requested by a skill
- **WHEN** runtime prepares engine configuration
- **THEN** the MCP configuration MUST be scoped to the current run
- **AND** it MUST NOT become visible to later runs that did not request it

### Requirement: Codex declared MCP MUST use a per-run profile
When a Codex run includes declared MCP, the runtime SHALL create a per-run Codex profile, launch Codex with that profile, and remove the profile after terminal completion.

#### Scenario: Codex run uses declared MCP
- **GIVEN** a Codex run resolves at least one declared MCP entry
- **WHEN** the Codex command is built
- **THEN** the command MUST select a per-run profile
- **AND** the per-run profile MUST contain the declared MCP configuration

#### Scenario: Codex run terminates
- **GIVEN** a Codex run used a per-run MCP profile
- **WHEN** the run reaches a terminal state
- **THEN** the runtime MUST attempt to remove the per-run profile
- **AND** cleanup failure MUST NOT change the terminal run outcome

