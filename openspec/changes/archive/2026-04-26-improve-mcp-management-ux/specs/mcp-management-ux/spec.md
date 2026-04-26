## ADDED Requirements

### Requirement: Guided MCP Setup
The system SHALL provide a guided MCP setup experience that collects connection details, activation policy, engine support, authentication, and save preview without exposing users to registry-specific secret reference syntax.

#### Scenario: User opens guided MCP setup
- **WHEN** a user opens the MCP configuration section on `/ui/engines`
- **THEN** the UI presents an add/edit flow organized around connection, enablement, authentication, and preview
- **AND** the user is not required to type pipe-delimited auth rows or registry `secret_id` values

### Requirement: Typed MCP Authentication Inputs
The system SHALL let users configure MCP authentication through typed choices for no auth, Bearer token, API key header, custom header, and env token.

#### Scenario: Bearer token auth is compiled to header auth
- **WHEN** a user selects Bearer token auth and enters a token
- **THEN** the UI builds an MCP upsert payload containing header auth with `Authorization` and `Bearer ` prefix

#### Scenario: Blank edit key preserves existing secret
- **WHEN** a user edits an MCP server with existing auth and leaves the key value blank
- **THEN** the UI indicates that the existing key will be preserved
- **AND** the upsert request does not require the raw key to be re-entered

### Requirement: Native MCP JSON Import
The system SHALL allow users to paste common native MCP JSON shapes and convert them into a previewable MCP server form state.

#### Scenario: Import common MCP root object
- **WHEN** a user pastes JSON containing `mcpServers`, `mcp_servers`, or `mcp`
- **THEN** the UI extracts server definitions into the MCP setup flow
- **AND** waits for the user to confirm server id, engine policy, activation, scope, and auth before saving

#### Scenario: Import unsupported JSON
- **WHEN** a user pastes JSON that cannot be mapped to stdio or HTTP/SSE MCP fields
- **THEN** the UI displays a validation error
- **AND** no MCP server is saved

### Requirement: Advanced MCP Editor Without Custom Line Syntax
The system SHALL preserve advanced MCP editing while replacing custom comma and pipe-delimited encodings with structured controls.

#### Scenario: Advanced user edits complete MCP definition
- **WHEN** a user switches to advanced mode
- **THEN** the UI exposes activation, scope, transport, engine filters, command/url, args, env auth, and header auth
- **AND** auth entries are edited as structured rows rather than `Header|Prefix|value` text

### Requirement: MCP Server List Summaries
The system SHALL present MCP servers with user-readable summaries of connection type, enablement policy, effective engines, auth state, and Claude agent-home persistence.

#### Scenario: List displays scan-friendly MCP metadata
- **WHEN** the MCP server list is rendered
- **THEN** each row shows the server id, connection summary, enablement summary, effective engines, auth state, and whether it is a Claude agent-home default candidate
