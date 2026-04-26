## Why

Skill-Runner now has registry-driven MCP governance, but operators still need to edit MCP servers outside the running system and the first registry version cannot represent authenticated MCP endpoints. The project needs a managed UI/API surface that persists runtime MCP configuration safely, supports secret-backed env/header auth, and preserves the strict no-inline-secret policy for skills and engine overrides.

## What Changes

- Add global MCP management endpoints for listing, upserting, and deleting registry-backed MCP servers.
- Add a runtime MCP registry under the data directory; keep the repo asset registry as read-only bootstrap/baseline.
- Add a runtime MCP secret store that accepts raw values only through management writes, stores registry secret references, masks responses, and cleans secrets on delete.
- Extend the MCP registry contract to allow structured `auth.env` and `auth.headers` references while continuing to reject raw secrets in registry files, skill manifests, skill engine configs, and runtime overrides.
- Resolve secret references during engine config composition:
  - stdio MCP servers receive environment variables.
  - HTTP/SSE MCP servers receive headers.
- Add an MCP configuration section to `/ui/engines` after Engine Auth and before Custom Providers with full CRUD for server definitions and secret-backed auth entries.
- Preserve existing default/declared activation, engine filtering, direct MCP root-key bypass rejection, and Codex per-run profile behavior.

## Capabilities

### New Capabilities

- `mcp-config-governance`: Extends the MCP registry governance capability with runtime registry persistence, structured secret references, secret-backed rendering, and management API semantics.

### Modified Capabilities

- `ui-engine-management`: Add an MCP management section to the Engine management page with full CRUD and masked auth state.
- `management-api-surface`: Add global MCP management API resources under `/v1/management/mcp/servers`.
- `engine-adapter-runtime-contract`: Require governed MCP renderers/composers to resolve env/header secret references into engine-native runtime configuration without exposing raw keys elsewhere.

## Impact

- Adds runtime MCP registry and secret-store services under `server/services/mcp`.
- Updates `server/contracts/schemas/mcp_registry.schema.json` to allow structured auth references and reject raw secret-bearing fields.
- Adds management request/response models and routes for MCP CRUD.
- Updates engine MCP rendering/composition for secret-backed env/header injection.
- Updates `server/assets/templates/ui/engines.html` and `/ui/engines` tests to include the MCP management section.
- Adds or expands MCP, management API, UI, schema, resolver, renderer, and secret-store tests.
