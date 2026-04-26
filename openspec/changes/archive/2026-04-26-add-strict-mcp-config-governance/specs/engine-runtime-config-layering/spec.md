## ADDED Requirements

### Requirement: Governed MCP MUST be a system-generated runtime config layer
Runtime configuration composition MUST include governed MCP renderer output as a system-generated layer. This layer MUST be merged after skill defaults and runtime overrides, and before enforced policy.

#### Scenario: MCP layer participates in runtime config composition
- **GIVEN** runtime resolves one or more governed MCP entries for a run
- **WHEN** the engine runtime config is composed
- **THEN** the MCP renderer output MUST be merged into the final config
- **AND** enforced policy MUST still have higher precedence than the MCP layer

#### Scenario: no governed MCP entries resolve
- **GIVEN** runtime resolves no governed MCP entries for a run
- **WHEN** the engine runtime config is composed
- **THEN** MCP composition MUST be a no-op
- **AND** existing non-MCP config layering behavior MUST remain unchanged

### Requirement: User-controlled config layers MUST NOT write MCP root keys
Skill engine config assets and request-side runtime config overrides MUST NOT directly write engine-native MCP root keys. The system MUST reject such inputs before engine launch.

#### Scenario: skill config contains MCP root key
- **WHEN** a skill engine config asset contains `mcpServers`, `mcp_servers`, or `mcp`
- **THEN** runtime config preparation MUST reject the run before engine launch

#### Scenario: runtime override contains MCP root key
- **WHEN** request-side runtime engine override contains `mcpServers`, `mcp_servers`, or `mcp`
- **THEN** runtime config preparation MUST reject the run before engine launch

### Requirement: Default MCP MAY be scoped to agent-home
Registry-owned default MCP entries MAY declare `scope="agent-home"` or `scope="run-local"`. Declared MCP entries MUST ignore agent-home scope and remain run-local.

#### Scenario: default MCP declares agent-home scope
- **GIVEN** a default MCP entry declares `scope="agent-home"`
- **AND** the entry supports the current engine
- **WHEN** runtime prepares MCP configuration
- **THEN** the entry MAY be written to the managed agent-home configuration for that engine

#### Scenario: declared MCP declares agent-home scope
- **GIVEN** a declared MCP entry declares or inherits an agent-home-like scope
- **WHEN** runtime resolves it for a skill
- **THEN** the entry MUST still be applied only to the current run

