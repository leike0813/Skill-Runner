## ADDED Requirements

### Requirement: Runtime MCP registry MUST override bootstrap assets
The system SHALL read mutable MCP server definitions from a runtime registry under the data directory, and SHALL use the packaged asset registry only when no runtime registry exists.

#### Scenario: Runtime registry exists
- **WHEN** runtime MCP governance loads server definitions
- **AND** the runtime registry file exists
- **THEN** the system MUST validate and use the runtime registry
- **AND** it MUST NOT merge in packaged asset registry entries implicitly

#### Scenario: Runtime registry is absent
- **WHEN** runtime MCP governance loads server definitions
- **AND** the runtime registry file does not exist
- **THEN** the system MUST validate and use the packaged asset registry as the effective baseline

#### Scenario: Runtime registry is invalid JSON
- **WHEN** the runtime registry file contains invalid JSON
- **THEN** the system MUST preserve the invalid content in a backup file
- **AND** it MUST recover to an empty valid runtime registry structure

### Requirement: MCP registry auth MUST use structured secret references
The MCP registry schema SHALL allow structured `auth.env` and `auth.headers` entries that reference runtime secrets, and SHALL continue to reject raw secret values in registry files.

#### Scenario: Registry stores env secret reference
- **WHEN** a registry server entry contains `auth.env` with an environment variable name and secret reference
- **THEN** registry validation MUST accept the entry
- **AND** the registry MUST NOT contain the raw secret value

#### Scenario: Registry stores header secret reference
- **WHEN** a registry server entry contains `auth.headers` with a header name, optional prefix, and secret reference
- **THEN** registry validation MUST accept the entry
- **AND** the registry MUST NOT contain the raw secret value

#### Scenario: Registry contains raw secret value
- **WHEN** a registry server entry contains raw header values, raw environment values, bearer tokens, or inline credential fields
- **THEN** registry validation MUST fail

### Requirement: MCP secret store MUST protect raw key visibility
The runtime secret store SHALL be the only persistent location for raw MCP auth values and management responses SHALL never include those raw values.

#### Scenario: Secret is written
- **WHEN** a management upsert request provides a raw MCP auth value
- **THEN** the system MUST store the raw value in the runtime secret store
- **AND** the registry MUST store only the corresponding secret reference

#### Scenario: Managed server is listed
- **WHEN** a client lists MCP servers through the management API
- **THEN** the response MUST include configured and masked auth state
- **AND** it MUST NOT include any raw secret value

#### Scenario: Managed server is deleted
- **WHEN** a client deletes an MCP server through the management API
- **THEN** the system MUST remove the server from the runtime registry
- **AND** it MUST remove secret-store entries associated with that server

### Requirement: MCP renderer MUST inject resolved auth by transport
The governed MCP renderer SHALL resolve registry secret references during runtime config composition and inject auth into the engine-native MCP payload according to transport.

#### Scenario: stdio server has env auth
- **WHEN** a resolved stdio MCP server has configured env auth references
- **THEN** the rendered MCP payload MUST include environment variables with resolved secret values

#### Scenario: HTTP server has header auth
- **WHEN** a resolved HTTP or SSE MCP server has configured header auth references
- **THEN** the rendered MCP payload MUST include headers with resolved secret values and configured prefixes

#### Scenario: Secret reference is missing
- **WHEN** a resolved MCP server references a secret that is absent from the secret store
- **THEN** runtime config composition MUST fail before engine launch

### Requirement: MCP bypass rejection MUST remain enforced
The system SHALL continue to reject direct MCP root keys in skill engine config files and runtime overrides, even after authenticated MCP management is added.

#### Scenario: Skill config writes MCP root key
- **WHEN** a skill engine config file contains `mcpServers`, `mcp_servers`, or `mcp`
- **THEN** the run MUST be rejected before engine launch

#### Scenario: Runtime override writes MCP root key
- **WHEN** a request-side runtime engine config override contains `mcpServers`, `mcp_servers`, or `mcp`
- **THEN** the run MUST be rejected before engine launch
