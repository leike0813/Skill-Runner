## ADDED Requirements

### Requirement: Management API MUST expose MCP server CRUD
The management API SHALL expose global MCP server list, upsert, and delete operations under `/v1/management/mcp/servers`.

#### Scenario: List MCP servers
- **WHEN** a client calls `GET /v1/management/mcp/servers`
- **THEN** the response MUST include all effective runtime MCP server definitions
- **AND** auth entries MUST be represented only as configured or masked state

#### Scenario: Upsert MCP server
- **WHEN** a client calls `PUT /v1/management/mcp/servers/{server_id}` with a valid server definition
- **THEN** the system MUST validate the definition using the MCP registry contract and engine filtering semantics
- **AND** persist the server definition to the runtime registry

#### Scenario: Delete MCP server
- **WHEN** a client calls `DELETE /v1/management/mcp/servers/{server_id}`
- **THEN** the system MUST remove the server from the runtime registry
- **AND** delete secret-store entries associated with that server

### Requirement: Management API MUST never echo raw MCP keys
The management API SHALL accept raw MCP auth values only on write requests and SHALL never return those raw values in any response.

#### Scenario: Upsert request contains raw key
- **WHEN** a client upserts an MCP server with raw env or header key values
- **THEN** the response MUST include only configured and masked auth state
- **AND** it MUST NOT include the raw submitted value

#### Scenario: List follows upsert
- **WHEN** a client lists MCP servers after a successful key upsert
- **THEN** the response MUST still omit all raw key values

### Requirement: Management API MUST reject invalid MCP management writes
The management API SHALL reject unknown engines, empty effective engine sets, raw secret fields in registry-shaped payloads, missing required transport fields, and missing raw values for newly introduced auth entries.

#### Scenario: New auth entry has no value
- **WHEN** a client creates an MCP auth entry that has no existing secret
- **AND** the request does not provide a raw value
- **THEN** the API MUST reject the write

#### Scenario: Transport fields are invalid
- **WHEN** a client submits a stdio server without command or an HTTP/SSE server without URL
- **THEN** the API MUST reject the write
