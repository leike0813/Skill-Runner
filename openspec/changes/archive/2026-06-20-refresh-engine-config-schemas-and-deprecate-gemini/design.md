## Overview

This change separates active engine support from historical engine file readability. Gemini follows the existing iFlow deprecation pattern: its source tree remains in the repository, but runtime registries no longer import, validate, upgrade, install, authenticate, or execute it.

## Schema Refresh Strategy

- Refresh only active engine schemas: `codex`, `claude`, `opencode`, and `qwen`.
- Keep schemas additive and forward-compatible by avoiding strict `additionalProperties: false` on large upstream config roots unless upstream requires it.
- Use official/upstream references:
  - Codex: OpenAI Codex configuration reference and advanced configuration docs.
  - Claude: official Claude Code settings docs and the referenced schemastore schema.
  - OpenCode: official `https://opencode.ai/config.json` schema and config/model docs.
  - Qwen: official Qwen Code configuration and modelProviders docs plus upstream repository docs.
- Validate local `bootstrap/default/enforced/ui_shell_*` config files against refreshed schemas after changes.

## Gemini Deprecation Strategy

- `ENGINE_KEYS` contains only active engines: `codex`, `opencode`, `claude`, `qwen`.
- `LEGACY_READONLY_ENGINE_KEYS` includes `iflow` and `gemini`.
- Active adapter registry, auth strategy service, model registry, upgrade manager, CLI manager, engine status cache, and UI selectors must derive from active engine keys.
- Read-only workspace/file browsing can still consider legacy workspace folders such as `.gemini`.
- Gemini code and data files stay in place for history inspection and future manual reference, but no active import chain should require Gemini adapter initialization.

## Compatibility

- New requests, temporary uploads, skill package installs, and MCP registry entries cannot target Gemini.
- Existing records that already reference Gemini are not migrated.
- Historical file browsing is best-effort and read-only; it must not re-enable execution, auth, model catalog, or upgrade actions.

## Failure Modes

- If a refreshed schema accidentally rejects current local engine config, startup/tests should fail early.
- If a stale code path still imports Gemini adapter for active runtime, adapter registry tests should catch it.
- If a skill package or MCP registry still accepts Gemini, contract tests should fail.
