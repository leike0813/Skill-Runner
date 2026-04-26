# mcp-config-governance Specification

## Purpose
TBD - created by archiving change add-strict-mcp-config-governance. Update Purpose after archive.
## Requirements
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

### Requirement: Runtime MCP registry MUST override bootstrap assets
The system SHALL read mutable MCP server definitions from a runtime registry under the data directory, and SHALL use the packaged asset registry only when no runtime registry exists.

#### Scenario: Runtime registry exists
- **WHEN** runtime MCP governance loads server definitions
- **AND** the runtime registry file exists
- **THEN** the system MUST validate and use the runtime registry
- **AND** it MUST NOT merge in packaged asset registry entries implicitly

#### Scenario: Runtime registry is absent
- **WHEN** runtime MCP governance loads server definitions
- **AND** the runtime registry file does not exist
- **THEN** the system MUST validate and use the packaged asset registry as the effective baseline

#### Scenario: Runtime registry is invalid JSON
- **WHEN** the runtime registry file contains invalid JSON
- **THEN** the system MUST preserve the invalid content in a backup file
- **AND** it MUST recover to an empty valid runtime registry structure

### Requirement: MCP registry auth MUST use structured secret references
The MCP registry schema SHALL allow structured `auth.env` and `auth.headers` entries that reference runtime secrets, and SHALL continue to reject raw secret values in registry files.

#### Scenario: Registry stores env secret reference
- **WHEN** a registry server entry contains `auth.env` with an environment variable name and secret reference
- **THEN** registry validation MUST accept the entry
- **AND** the registry MUST NOT contain the raw secret value

#### Scenario: Registry stores header secret reference
- **WHEN** a registry server entry contains `auth.headers` with a header name, optional prefix, and secret reference
- **THEN** registry validation MUST accept the entry
- **AND** the registry MUST NOT contain the raw secret value

#### Scenario: Registry contains raw secret value
- **WHEN** a registry server entry contains raw header values, raw environment values, bearer tokens, or inline credential fields
- **THEN** registry validation MUST fail

### Requirement: MCP secret store MUST protect raw key visibility
The runtime secret store SHALL be the only persistent location for raw MCP auth values and management responses SHALL never include those raw values.

#### Scenario: Secret is written
- **WHEN** a management upsert request provides a raw MCP auth value
- **THEN** the system MUST store the raw value in the runtime secret store
- **AND** the registry MUST store only the corresponding secret reference

#### Scenario: Managed server is listed
- **WHEN** a client lists MCP servers through the management API
- **THEN** the response MUST include configured and masked auth state
- **AND** it MUST NOT include any raw secret value

#### Scenario: Managed server is deleted
- **WHEN** a client deletes an MCP server through the management API
- **THEN** the system MUST remove the server from the runtime registry
- **AND** it MUST remove secret-store entries associated with that server

### Requirement: MCP renderer MUST inject resolved auth by transport
The governed MCP renderer SHALL resolve registry secret references during runtime config composition and inject auth into the engine-native MCP payload according to transport.

#### Scenario: stdio server has env auth
- **WHEN** a resolved stdio MCP server has configured env auth references
- **THEN** the rendered MCP payload MUST include environment variables with resolved secret values

#### Scenario: HTTP server has header auth
- **WHEN** a resolved HTTP or SSE MCP server has configured header auth references
- **THEN** the rendered MCP payload MUST include headers with resolved secret values and configured prefixes

#### Scenario: Secret reference is missing
- **WHEN** a resolved MCP server references a secret that is absent from the secret store
- **THEN** runtime config composition MUST fail before engine launch

### Requirement: MCP bypass rejection MUST remain enforced
The system SHALL continue to reject direct MCP root keys in skill engine config files and runtime overrides, even after authenticated MCP management is added.

#### Scenario: Skill config writes MCP root key
- **WHEN** a skill engine config file contains `mcpServers`, `mcp_servers`, or `mcp`
- **THEN** the run MUST be rejected before engine launch

#### Scenario: Runtime override writes MCP root key
- **WHEN** a request-side runtime engine config override contains `mcpServers`, `mcp_servers`, or `mcp`
- **THEN** the run MUST be rejected before engine launch

### Requirement: Claude MCP MUST use Claude active state materialization
The system SHALL materialize governed MCP servers for Claude into Claude Code's active state file instead of the generic `settings.json` MCP root.

#### Scenario: Claude default agent-home MCP is materialized
- **WHEN** a managed MCP registry entry is `activation="default"`, supports `claude`, and has `scope="agent-home"`
- **THEN** the system MUST write that MCP server under the Claude active state top-level `mcpServers`
- **AND** it MUST NOT write that server into `run_dir/.claude/settings.json`

#### Scenario: Claude run-local MCP is materialized
- **WHEN** a Claude run resolves a run-local MCP server
- **THEN** the system MUST write that MCP server under `projects[str(run_dir.resolve())].mcpServers` in the Claude active state file

### Requirement: Claude MCP auth MUST be secret-resolved in active state
The system SHALL resolve governed MCP auth references before writing Claude MCP state and SHALL keep raw secrets out of the registry and management responses.

#### Scenario: Claude HTTP server uses bearer header
- **WHEN** a Claude HTTP or SSE MCP server has an auth header reference with prefix `Bearer `
- **THEN** the materialized Claude MCP payload MUST contain `headers.Authorization` with the resolved `Bearer <secret>` value

#### Scenario: Claude stdio server uses env auth
- **WHEN** a Claude stdio MCP server has env auth references
- **THEN** the materialized Claude MCP payload MUST contain `env` values resolved from the secret store

### Requirement: Claude MCP deletion MUST preserve unmanaged user entries
The system SHALL remove only Skill-Runner-managed Claude MCP entries during management delete or run cleanup.

#### Scenario: Managed Claude MCP is deleted
- **WHEN** a management request deletes a Claude agent-home MCP server managed by Skill-Runner
- **THEN** the system MUST remove that server from active state top-level `mcpServers`
- **AND** it MUST preserve unrelated user-configured MCP servers

