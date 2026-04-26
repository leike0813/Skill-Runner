## 1. Claude Active State

- [x] 1.1 Add a Claude active state helper for `agent_home/.claude/.claude.json` and legacy `agent_home/.claude.json`
- [x] 1.2 Update Claude bootstrap layout and trust registry defaults to use the active state file
- [x] 1.3 Add legacy migration and invalid JSON recovery coverage

## 2. Claude MCP Materialization

- [x] 2.1 Implement Claude MCP state materializer for top-level and project-scoped `mcpServers`
- [x] 2.2 Resolve env/header auth secrets into Claude MCP payloads
- [x] 2.3 Remove Claude governed MCP merging from `run_dir/.claude/settings.json`
- [x] 2.4 Add terminal cleanup for run-local Claude MCP entries without affecting run outcomes

## 3. Management Sync

- [x] 3.1 Synchronize Claude `default + agent-home` MCP to active state on management upsert
- [x] 3.2 Remove managed Claude agent-home MCP from active state on management delete
- [x] 3.3 Preserve unmanaged Claude MCP entries during sync and delete

## 4. Tests and Verification

- [x] 4.1 Add/update Claude config composer, trust/bootstrap, management API, and MCP governance tests
- [x] 4.2 Run targeted pytest suite for MCP, management API, Claude composer, agent layout, and trust manager
- [x] 4.3 Run `openspec validate fix-claude-mcp-active-state-materialization --strict`
