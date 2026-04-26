## Why

Skill-Runner is adding MCP support across multiple CLI engines, but direct per-engine MCP configuration would allow skills or runtime overrides to bypass governance and expose tools inconsistently. The project needs a single registry-driven MCP contract that can safely default selected tools per engine while requiring explicit skill opt-in for restricted tools.

## What Changes

- Add a system-owned MCP registry with machine-readable validation.
- Introduce two MCP activation classes:
  - `default`: automatically enabled for matching engines.
  - `declared`: enabled only when a skill explicitly references the registry ID.
- Allow registry entries to scope default enablement by `engines` and `unsupported_engines`, using the same effective-engine semantics as skill manifests.
- Add `runner.json.mcp.required_servers` so skills can request declared MCP servers by ID.
- Reject unknown MCP IDs, engine-incompatible MCP IDs, and unsupported MCP fields before launch.
- Reject first-version secret-bearing MCP configuration, including env/header/secret fields.
- Render governed MCP entries into each engine's native config shape:
  - Codex: `mcp_servers`
  - Gemini/Qwen/Claude: `mcpServers`
  - OpenCode: `mcp`
- Prevent skill engine config and runtime overrides from directly writing MCP root keys.
- Keep declared MCP run-local only; allow default MCP registry entries to choose `run-local` or `agent-home` scope when engine-compatible.
- For Codex, use a per-run profile for declared MCP and clean it up after terminal run completion.

## Capabilities

### New Capabilities

- `mcp-config-governance`: Defines the system MCP registry, activation classes, engine filtering, skill declarations, validation policy, and engine-specific rendering rules.

### Modified Capabilities

- `skill-package-validation-schema`: Allow and validate `runner.json.mcp.required_servers` while continuing to reject inline MCP definitions.
- `engine-runtime-config-layering`: Add governed MCP as a system-generated runtime config layer and define its precedence relative to skill defaults, runtime overrides, and enforced policy.
- `engine-adapter-runtime-contract`: Require adapters/composers to consume governed MCP renderer output and prevent direct MCP root-key bypass through engine-specific config inputs.

## Impact

- Adds `server/contracts/schemas/mcp_registry.schema.json` and `server/assets/configs/mcp_registry.json`.
- Updates `server/contracts/schemas/skill/skill_runner_manifest.schema.json` and `SkillManifest` models.
- Adds Python service modules for MCP registry loading, policy resolution, and engine rendering.
- Updates Codex, Gemini, Qwen, Claude, and OpenCode config composers.
- Adds unit coverage for registry validation, resolver policy, renderer mapping, bypass guards, composer integration, and Codex per-run profile cleanup.
- No new Node dependency, no Admin UI/API in the first version, and no support for secret/env/header MCP entries in this change.
