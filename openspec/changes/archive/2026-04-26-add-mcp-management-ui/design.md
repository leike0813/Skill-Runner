## Context

The existing MCP governance implementation is registry-driven and engine-aware, but the registry is a repo asset and the first version explicitly rejects env/header/secret fields. Engine operators need a runtime-controlled management surface that can add or edit MCP servers without modifying tracked files, while the runtime still prevents skills and request overrides from injecting arbitrary MCP roots or raw secrets.

The Engine management UI already contains authentication controls and custom provider management. The MCP UI belongs in that same operational surface, after Engine Auth and before Custom Providers, because MCP server availability is an engine/runtime concern rather than a per-skill authoring concern.

## Goals / Non-Goals

**Goals:**

- Provide global MCP CRUD APIs and a `/ui/engines` management section.
- Store mutable MCP server definitions in `DATA_DIR`, with assets registry as bootstrap fallback only.
- Store raw MCP auth keys in a runtime secret store and keep registry entries limited to secret references.
- Mask all management responses and UI state; never echo raw secrets after write.
- Resolve env/header auth during engine config composition for Codex, Gemini, Qwen, Claude, and OpenCode.
- Preserve strict activation, declared/default engine filtering, and direct MCP root-key bypass rejection.

**Non-Goals:**

- Encrypting secrets at rest.
- Per-user or per-skill MCP management permissions.
- Importing MCP definitions from third-party config tools.
- Changing custom provider key storage semantics.
- Allowing skills, skill engine config files, or runtime overrides to inline raw MCP auth values.

## Decisions

### Runtime Registry Over Repo Mutation

The service writes a runtime registry file under `DATA_DIR` and treats `server/assets/configs/mcp_registry.json` as a read-only bootstrap baseline. This avoids modifying repo-tracked assets from the UI and allows deployments to keep packaged defaults separate from local operator changes.

When the runtime registry file does not exist, reads fall back to the asset registry. The first management write materializes the effective registry into `DATA_DIR`. Invalid runtime registry JSON is backed up and replaced with an empty structure so the service can recover to a known writable state.

### Structured Auth References Only

Registry entries gain an `auth` object with `env` and `headers` arrays. Each auth entry stores names and secret references, never raw values. Management upsert requests are the only path that accepts raw values; the service converts them into deterministic secret IDs and persists the values in the runtime secret store.

Blank auth values during edit mean "preserve existing secret" when a matching entry already exists. Blank values for new auth entries are rejected because there is no existing secret to preserve.

### Masked Management Views

Management responses return `configured` plus masked display state for env/header auth entries. They do not return raw values and do not require callers to know secret IDs. Delete operations remove the server and all secret references that belonged to the deleted server.

### Renderer-Time Secret Resolution

The MCP resolver keeps producing governed server definitions using the existing activation and engine filtering rules. Engine renderers resolve secret references at composition time:

- stdio transports inject auth env variables into the rendered server payload.
- HTTP/SSE transports inject auth headers into the rendered server payload.
- Missing secret values fail before engine launch.

Codex keeps using `mcp_servers` and per-run profiles for declared run-local MCP. JSON-based engines keep using `mcpServers`; OpenCode keeps using `mcp`.

### UI Integration Without New Dependencies

The MCP UI is implemented in the existing `engines.html` template using the current fetch/status/error styling conventions. It adds a focused CRUD card and does not add a frontend build step or dependency.

## Risks / Trade-offs

- Raw secrets are stored in a local JSON file rather than encrypted storage -> mitigate with no API echo, best-effort `0600`, and secret refs outside the registry.
- Runtime registry recovery from invalid JSON may discard malformed content from active use -> mitigate by backing up the invalid file before replacing it.
- Engine-native header field names differ across CLIs -> mitigate with renderer tests for the project-supported config shapes and keep mappings centralized.
- UI forms can become dense -> mitigate by keeping the MCP section operational and table-driven, with blank secret inputs preserving existing values.
