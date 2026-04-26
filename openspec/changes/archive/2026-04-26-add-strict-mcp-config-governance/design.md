## Context

Skill-Runner already builds engine runtime configuration in Python through adapter-specific composers and shared config layering. MCP configuration is currently only represented indirectly inside individual engine config schemas, which means a skill or request-side override could add MCP roots in engine-specific formats without a system policy gate.

This change introduces a system-owned MCP registry and resolver. The registry is the only source of MCP server command/url definitions. Skills may only reference declared registry IDs, and the runtime renders resolved entries into the current engine's config shape.

## Goals / Non-Goals

**Goals:**

- Provide strict, Python-native MCP governance without adding Node runtime dependencies.
- Support default MCP servers that can be enabled per engine.
- Support restricted MCP servers that require explicit skill declaration.
- Reject unknown, engine-incompatible, secret-bearing, or bypassed MCP configuration before engine launch.
- Integrate governed MCP with existing engine config composers and enforced policy precedence.
- Keep declared MCP run-local, including Codex via a per-run profile.

**Non-Goals:**

- No Admin UI or Admin API in this version.
- No secret/env/header-bearing MCP entries in this version.
- No skill-authored inline MCP command/url definitions.
- No automatic import from external MCP registries.
- No broad refactor of engine config composition beyond the MCP insertion and guard points.

## Decisions

1. **Use a system registry as the MCP source of truth.**

   Add `server/assets/configs/mcp_registry.json` validated by `server/contracts/schemas/mcp_registry.schema.json`. Each entry declares activation class, optional engine policy, scope, transport, and command/url data.

   Alternative considered: allow skills to inline MCP definitions. Rejected because arbitrary commands in skill packages would bypass review and make supply-chain risk harder to audit.

2. **Reuse engine allow/exclude semantics for registry entries.**

   Registry entries support `engines` and `unsupported_engines`; omitted `engines` means all supported engines. The resolver computes effective engines using the same semantics as skill manifest engine policy, then checks the current run engine.

   Alternative considered: use ad hoc fields such as `default_for`. Rejected because it would duplicate existing policy concepts and create drift.

3. **Insert governed MCP as a system-generated config layer.**

   For each run, composers receive or compute MCP renderer output and merge it after skill defaults/runtime overrides and before enforced policy. This lets enforced config retain final authority while preventing user-controlled layers from bypassing the registry.

   Alternative considered: write MCP directly into engine defaults. Rejected because declared MCP is skill/run-specific and must not become globally visible.

4. **Reject direct MCP root-key bypass.**

   Skill engine config assets and request-side runtime config overrides must not contain engine-native MCP root keys (`mcpServers`, `mcp_servers`, `mcp`). The system must fail before launch instead of silently removing these keys.

   Alternative considered: strip bypass keys. Rejected because silent stripping makes skill behavior hard to diagnose.

5. **Keep declared MCP run-local only.**

   Declared MCP must only affect the run whose skill requested it. For JSON-config engines this means the run-local config file. For Codex, which currently writes a profile into agent-home config, the runtime uses a per-run profile and switches the command to that profile, then cleans it up on terminal completion.

   Alternative considered: write declared MCP into the shared `skill-runner` Codex profile. Rejected because later runs would inherit restricted tools.

6. **No secrets in the first version.**

   Registry schema rejects env, headers, bearer token refs, and other secret-bearing fields. This keeps the first implementation deterministic and avoids introducing a partial secret store.

## Risks / Trade-offs

- **Risk: Codex per-run profile cleanup can fail** -> The terminal cleanup path should log a warning and leave the run outcome unchanged; periodic cleanup can be added later if stale profiles become a problem.
- **Risk: existing skills with MCP roots in engine config start failing** -> This is intentional governance. The error should name the blocked key and point to registry-based MCP declarations.
- **Risk: default agent-home MCP may surprise users across runs** -> Only registry-owned `default` entries can choose `agent-home`; declared entries cannot.
- **Risk: schemas for external engines drift** -> Renderer tests should pin the current mappings and be updated when engine config contracts change.

## Migration Plan

1. Add registry schema and an initially empty or minimal registry file.
2. Add manifest field support and validation for `mcp.required_servers`.
3. Add resolver/renderer services and bypass guards.
4. Wire engine composers to merge governed MCP output.
5. Add Codex per-run profile selection and cleanup.
6. Update docs/specs and unit tests.

Rollback is straightforward before registry entries are added: remove the MCP registry file, manifest field support, and composer insertion. Existing non-MCP runtime behavior should remain unchanged.

## Open Questions

- Which MCP servers should ship as initial `default` registry entries is intentionally left to configuration, not hard-coded implementation.
