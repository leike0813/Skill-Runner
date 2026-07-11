## ADDED Requirements

### Requirement: Kilo governed MCP MUST be system-generated

Kilo MCP configuration SHALL be written only by governed MCP rendering in phase 1.

#### Scenario: Kilo user config contains mcp root

- **WHEN** a Kilo skill config or runtime override contains top-level `mcp`
- **THEN** runtime config preparation MUST reject the run before engine launch

#### Scenario: Governed MCP resolves for Kilo

- **WHEN** governed MCP entries resolve for a Kilo run
- **THEN** the Kilo config composer MAY write the generated Kilo `mcp` layer into `.kilo/kilo.jsonc`
## Requirements

### Requirement: CodeBuddy governed MCP MUST be system generated

The MCP registry MUST render CodeBuddy configuration under mcpServers, include required transport type values for STDIO, HTTP, and SSE entries, and resolve secrets through the existing secret resolver.

#### Scenario: No MCP servers are enabled
- **WHEN** a run is materialized with an empty governed registry
- **THEN** .codebuddy/mcp.json contains an empty mcpServers object and the command still uses --strict-mcp-config
### Requirement: CodeBuddy MUST exclude unmanaged MCP sources

Every start and resume command MUST pass the generated MCP file with strict mode so host, user, and undeclared project MCP sources are not loaded.

#### Scenario: Host has user-level MCP configuration
- **WHEN** a managed CodeBuddy attempt starts
- **THEN** only servers in the run-local generated file are eligible for loading

#### Scenario: CodeBuddy inline terminal starts
- **WHEN** a managed CodeBuddy TUI launch is prepared
- **THEN** it receives a session-local empty mcpServers file through --mcp-config and --strict-mcp-config and cannot load host MCP
### Requirement: Kilo governed MCP MUST match OpenCode's native configuration

The shared MCP renderer MUST render Kilo servers under the top-level `mcp` key using the same STDIO, HTTP, SSE, environment, and header payload shapes as OpenCode. Kilo MUST NOT maintain a copied renderer.

#### Scenario: A Kilo run enables a governed server
- **WHEN** the registry resolves a server for engine `kilo`
- **THEN** the run-local Kilo config contains that server under `mcp` and direct MCP roots from skill or runtime configuration remain rejected

