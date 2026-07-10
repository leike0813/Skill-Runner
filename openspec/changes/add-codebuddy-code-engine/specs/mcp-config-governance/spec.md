## ADDED Requirements

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
