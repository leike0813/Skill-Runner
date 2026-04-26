## ADDED Requirements

### Requirement: runner manifest MUST allow governed MCP declarations
`assets/runner.json` MUST allow an optional `mcp.required_servers` array containing registry server IDs required by the skill. The field MUST contain unique non-empty strings and MUST NOT contain inline MCP definitions.

#### Scenario: required MCP servers pass manifest validation
- **WHEN** `runner.json.mcp.required_servers` is an array of unique non-empty strings
- **THEN** skill package manifest validation MUST accept the field

#### Scenario: required MCP servers has invalid shape
- **WHEN** `runner.json.mcp.required_servers` is not an array of unique non-empty strings
- **THEN** skill package manifest validation MUST reject the manifest

#### Scenario: inline MCP definition is present
- **WHEN** `runner.json.mcp` contains an inline server object with command, URL, env, header, or secret data
- **THEN** skill package manifest validation MUST reject the manifest

