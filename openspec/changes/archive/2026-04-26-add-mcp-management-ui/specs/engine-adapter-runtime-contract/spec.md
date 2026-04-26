## ADDED Requirements

### Requirement: Engine adapters MUST consume secret-resolved governed MCP config
Engine adapters SHALL consume MCP renderer output after runtime secret references have been resolved and SHALL keep raw MCP secrets out of skill manifests, skill config assets, runtime overrides, logs, and management responses.

#### Scenario: Codex MCP config includes resolved auth
- **WHEN** Codex runtime config composition renders a governed MCP server with auth
- **THEN** the adapter MUST receive the auth under the Codex-native MCP root
- **AND** declared run-local MCP behavior MUST continue to use per-run profile selection and cleanup

#### Scenario: JSON MCP engines include resolved auth
- **WHEN** Gemini, Qwen, or Claude runtime config composition renders a governed MCP server with auth
- **THEN** the adapter MUST receive the auth under `mcpServers`

#### Scenario: OpenCode MCP config includes resolved auth
- **WHEN** OpenCode runtime config composition renders a governed MCP server with auth
- **THEN** the adapter MUST receive the auth under `mcp`

#### Scenario: Direct root bypass remains rejected
- **WHEN** an engine adapter receives skill config or runtime override input containing a native MCP root
- **THEN** the adapter or shared composer MUST reject that input before applying governed MCP output
