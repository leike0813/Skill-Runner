## ADDED Requirements

### Requirement: Engine Management MCP Section Uses Friendly UX
The Engine management page SHALL expose MCP management through a guided user experience with typed authentication, native JSON import, advanced editing, and masked key preservation.

#### Scenario: Engine page renders improved MCP controls
- **WHEN** a user opens `/ui/engines`
- **THEN** the MCP section includes controls for guided add/edit, native JSON import, typed authentication, and advanced mode
- **AND** the page does not require users to enter pipe-delimited auth syntax

#### Scenario: Existing MCP CRUD behavior remains available
- **WHEN** a user saves or deletes an MCP server through the improved MCP section
- **THEN** the UI uses the existing MCP management CRUD endpoints
- **AND** runtime registry and secret handling semantics remain unchanged
