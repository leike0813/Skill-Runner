## Context

Skill-Runner launches Claude with `HOME=<agent_home>` and `CLAUDE_CONFIG_DIR=<agent_home>/.claude`. Claude Code 2.1.116 reads and writes MCP configuration from `$CLAUDE_CONFIG_DIR/.claude.json`, which resolves to `agent_home/.claude/.claude.json`. Current MCP governance renders Claude MCP config into `run_dir/.claude/settings.json`, so managed Claude MCP servers do not appear in `claude mcp list` and are not available to runs.

## Goals / Non-Goals

**Goals:**
- Use a single Claude active state path matching the runtime environment.
- Materialize governed Claude MCP into Claude Code's active state file.
- Keep `agent-home` default MCP persistent and keep run-local MCP scoped to the current run project entry.
- Preserve existing registry, secret-store, and non-Claude engine behavior.

**Non-Goals:**
- Do not change MCP registry or secret-store public schema.
- Do not introduce a new UI workflow.
- Do not invoke `claude mcp add` at runtime; materialization remains Python-native and registry-driven.

## Decisions

- Add a Claude state helper that returns `agent_home/.claude/.claude.json` and identifies legacy `agent_home/.claude.json` only as an optional migration source. This matches the `CLAUDE_CONFIG_DIR` behavior verified with `claude mcp list` and `claude mcp add-json`.
- Add a Claude MCP materializer instead of extending the generic renderer. Claude's MCP storage model differs from JSON settings engines, so using a dedicated writer prevents future regressions.
- Map registry scopes to Claude state scopes directly: `agent-home` writes top-level `mcpServers`; `run-local` writes `projects[str(run_dir.resolve())].mcpServers`.
- Use atomic JSON writes and backup invalid JSON before recovery. Active state contains user-owned Claude data, so writes must preserve unrelated keys.
- Track Skill-Runner-managed Claude MCP IDs in a sidecar under `agent_home/.claude/` so delete/cleanup operations remove only managed entries.

## Risks / Trade-offs

- Active state may already contain user MCP servers with the same ID. Mitigation: Skill-Runner overwrites only IDs it manages and records managed IDs in the sidecar.
- Legacy `agent_home/.claude.json` may contain trust or user state. Mitigation: migrate only when active state is absent, and preserve active state as authoritative once present.
- Run-local cleanup through project entry removal may also remove trust state for the run path. Mitigation: this matches existing terminal trust cleanup semantics for run folders.
