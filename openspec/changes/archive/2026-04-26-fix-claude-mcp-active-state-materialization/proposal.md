## Why

Claude MCP configuration currently materializes into `run_dir/.claude/settings.json`, but Skill-Runner launches Claude with `CLAUDE_CONFIG_DIR=agent_home/.claude`, and Claude Code reads MCP state from `agent_home/.claude/.claude.json`. As a result, MCP servers configured through management UI can be persisted in the registry but remain invisible to Claude.

## What Changes

- Add Claude-specific active state handling for `agent_home/.claude/.claude.json`.
- Materialize Claude MCP servers into Claude Code's active state file instead of per-run `settings.json`.
- Map `agent-home` MCP scope to top-level Claude `mcpServers`.
- Map `run-local` MCP scope to the current run project's `projects[run_dir].mcpServers`.
- Update Claude bootstrap/trust paths to use the same active state file.
- Preserve compatibility with legacy `agent_home/.claude.json` by using it only as a migration source.

## Capabilities

### New Capabilities

### Modified Capabilities
- `mcp-config-governance`: Claude MCP materialization must use Claude Code's active MCP state file rather than generic settings roots.
- `engine-runtime-config-layering`: Claude governed MCP is no longer merged into `settings.json`; it is materialized through a Claude-specific state writer.
- `engine-adapter-runtime-contract`: Claude adapter runtime must prepare and clean up MCP state using Claude Code's active state semantics.
- `trust-config-bootstrap`: Claude bootstrap/trust state must target the active state file used by the runtime environment.
- `management-api-surface`: Claude agent-home MCP writes and deletes must synchronize the active state file.

## Impact

- Affects Claude adapter config composition, MCP registry/rendering integration, management MCP CRUD side effects, and Claude trust/bootstrap path handling.
- Does not change MCP registry or secret-store public schema.
- Does not change non-Claude MCP behavior.
