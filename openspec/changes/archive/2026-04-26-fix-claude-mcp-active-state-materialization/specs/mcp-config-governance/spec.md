## ADDED Requirements

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

