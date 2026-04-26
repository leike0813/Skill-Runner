## ADDED Requirements

### Requirement: Engine management UI MUST include MCP configuration
The Engine management page SHALL include an MCP configuration section after Engine Auth and before Custom Providers.

#### Scenario: Engine management page renders MCP section
- **WHEN** a user opens `/ui/engines`
- **THEN** the page MUST render a distinct MCP configuration section
- **AND** the section MUST appear after Engine Auth controls and before Custom Providers

### Requirement: MCP UI MUST support full server CRUD
The MCP configuration section SHALL allow users to create, edit, and delete MCP server definitions through the management API.

#### Scenario: User creates an MCP server
- **WHEN** the user submits a valid MCP server form
- **THEN** the UI MUST call the MCP server upsert API
- **AND** refresh the server list after success

#### Scenario: User edits an MCP server
- **WHEN** the user selects an existing MCP server for edit
- **THEN** the UI MUST populate editable non-secret fields
- **AND** secret inputs MUST remain blank to mean preserve existing configured values

#### Scenario: User deletes an MCP server
- **WHEN** the user requests deletion of an MCP server
- **THEN** the UI MUST require confirmation
- **AND** call the MCP server delete API after confirmation

### Requirement: MCP UI MUST mask auth keys
The MCP configuration section SHALL display only configured or masked state for MCP auth keys and SHALL never display raw key values.

#### Scenario: Server list includes configured auth
- **WHEN** the UI renders a managed MCP server with auth entries
- **THEN** the UI MUST show whether each entry is configured
- **AND** it MUST NOT render raw key values

#### Scenario: User replaces a key
- **WHEN** the user enters a new env or header key value while editing
- **THEN** the UI MUST submit the new raw value only in the upsert request
- **AND** the refreshed view MUST show only masked state
