## ADDED Requirements

### Requirement: Claude governed MCP MUST bypass generic settings merge
Claude runtime config composition SHALL resolve governed MCP entries but SHALL NOT merge the generic MCP renderer output into `run_dir/.claude/settings.json`.

#### Scenario: Claude config composer resolves MCP
- **WHEN** the Claude config composer prepares a run with governed MCP entries
- **THEN** it MUST invoke Claude active state materialization for those entries
- **AND** the generated `run_dir/.claude/settings.json` MUST NOT contain `mcpServers`

#### Scenario: Non-Claude engines retain generic MCP layering
- **WHEN** Gemini, Qwen, Codex, or OpenCode prepares governed MCP configuration
- **THEN** the existing engine-native MCP rendering and layering behavior MUST remain unchanged

