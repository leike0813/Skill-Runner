## MODIFIED Requirements

### Requirement: MCP engine scopes MUST use active engine enum

MCP registry entries MUST target only active supported engines.

#### Scenario: MCP registry rejects Gemini scope
- **WHEN** an MCP registry entry declares `engines` or `unsupported_engines` containing `gemini`
- **THEN** MCP registry validation MUST reject the entry as unsupported
