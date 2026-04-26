## Why

The current MCP management UI exposes the low-level registry contract directly, which makes common MCP setup difficult even for users familiar with agent tools. Auth setup is especially error-prone because users must manually translate common patterns like Bearer tokens into header/prefix/value rows.

## What Changes

- Replace the default MCP editing experience with a guided flow for connection details, engine/activation scope, auth type, preview, and save.
- Keep an advanced editor for complete existing capabilities, but replace line-based header/env/args syntax with structured controls.
- Add a paste/import entry for native MCP JSON from common agent tools, converting it into the existing management API payload only after preview confirmation.
- Add typed auth choices for no auth, Bearer token, API key header, custom header, and env token, while preserving write-only key semantics.
- Improve MCP server list summaries so users can scan connection type, enablement policy, engine support, auth state, and Claude agent-home persistence status.
- Preserve the existing registry, secret store, management API, resolver, and renderer contracts.

## Capabilities

### New Capabilities

- `mcp-management-ux`: Covers the guided MCP configuration experience, typed auth inputs, native JSON import, advanced editor behavior, and user-facing list summaries.

### Modified Capabilities

- `ui-engine-management`: The Engine management page must expose the improved MCP management UX while preserving existing CRUD behavior.

## Impact

- Updates `/ui/engines` template JavaScript and markup for the MCP section.
- Adds or expands UI route/template tests for the guided controls, import entry, and removal of raw line-format auth instructions.
- Does not change public MCP management endpoints, registry persistence schema, runtime secret storage, or engine runtime rendering semantics.
