## ADDED Requirements

### Requirement: Kilo governed MCP MUST be system-generated

Kilo MCP configuration SHALL be written only by governed MCP rendering in phase 1.

#### Scenario: Kilo user config contains mcp root

- **WHEN** a Kilo skill config or runtime override contains top-level `mcp`
- **THEN** runtime config preparation MUST reject the run before engine launch

#### Scenario: Governed MCP resolves for Kilo

- **WHEN** governed MCP entries resolve for a Kilo run
- **THEN** the Kilo config composer MAY write the generated Kilo `mcp` layer into `.kilo/kilo.jsonc`
