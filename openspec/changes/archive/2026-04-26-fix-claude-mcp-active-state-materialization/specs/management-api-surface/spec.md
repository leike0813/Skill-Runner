## ADDED Requirements

### Requirement: MCP management MUST synchronize Claude agent-home MCP
The management API SHALL synchronize Claude active state when a managed MCP server is saved or deleted as a default agent-home Claude MCP.

#### Scenario: Claude agent-home MCP is saved
- **WHEN** a client upserts an MCP server that is `activation="default"`, supports `claude`, and has `scope="agent-home"`
- **THEN** the API MUST persist the registry entry
- **AND** it MUST materialize that server under active state top-level `mcpServers`

#### Scenario: Claude agent-home MCP is deleted
- **WHEN** a client deletes a managed MCP server that had been materialized for Claude agent-home use
- **THEN** the API MUST remove the managed active state entry
- **AND** it MUST preserve unrelated Claude MCP servers
