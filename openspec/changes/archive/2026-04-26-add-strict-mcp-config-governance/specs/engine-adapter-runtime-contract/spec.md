## ADDED Requirements

### Requirement: Engine config composers MUST consume governed MCP renderer output
Engine config composers MUST receive or compute governed MCP renderer output and merge it through the shared runtime config layering path. Engine-specific composers MUST NOT independently parse skill MCP declarations.

#### Scenario: composer receives governed MCP config
- **WHEN** an engine config composer prepares the config for a run
- **THEN** governed MCP renderer output MUST be available as a dedicated system-generated layer
- **AND** composer behavior MUST use the engine-native root shape produced by the renderer

### Requirement: Adapter runtime MUST reject MCP bypass inputs before launch
Adapter runtime preparation MUST fail fast when user-controlled config contains direct MCP root keys.

#### Scenario: bypass key reaches adapter preparation
- **WHEN** adapter runtime preparation sees `mcpServers`, `mcp_servers`, or `mcp` from skill defaults or runtime overrides
- **THEN** it MUST raise a configuration error before building the engine command

### Requirement: Codex adapter MUST support per-run MCP profiles
Codex adapter runtime MUST support selecting a per-run profile when governed MCP resolution includes declared MCP entries.

#### Scenario: per-run profile is selected
- **GIVEN** governed MCP resolution for a Codex run includes declared MCP
- **WHEN** the Codex adapter builds the start or resume command
- **THEN** the command MUST select the per-run profile that contains those MCP entries

#### Scenario: per-run profile cleanup is requested
- **GIVEN** a Codex run used a per-run MCP profile
- **WHEN** orchestration performs terminal cleanup
- **THEN** it MUST invoke Codex profile cleanup for that run profile

