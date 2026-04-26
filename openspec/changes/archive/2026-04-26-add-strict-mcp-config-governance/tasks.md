## 1. Contracts and Registry

- [x] 1.1 Add `server/contracts/schemas/mcp_registry.schema.json` with registry entry validation for `activation`, `engines`, `unsupported_engines`, `scope`, `transport`, `command`, `args`, and `url`
- [x] 1.2 Add `server/assets/configs/mcp_registry.json` as the system-owned MCP registry source of truth
- [x] 1.3 Reject secret-bearing registry fields such as `env`, `headers`, bearer token references, credential references, and secret references in schema validation
- [x] 1.4 Update skill manifest schema/model validation to allow `runner.json.mcp.required_servers` as unique non-empty registry IDs
- [x] 1.5 Reject inline skill MCP server definitions, commands, URLs, env, headers, or secrets in `runner.json`

## 2. MCP Resolution and Rendering

- [x] 2.1 Implement an MCP registry loader that validates the registry schema before runtime use
- [x] 2.2 Implement resolver logic for `default` and `declared` activation classes
- [x] 2.3 Implement engine filtering with `effective_engines = (engines if provided else all_supported) - unsupported_engines`
- [x] 2.4 Reject unknown declared MCP IDs before engine launch
- [x] 2.5 Reject declared MCP IDs that do not support the current engine before engine launch
- [x] 2.6 Enforce declared MCP as `run-local` regardless of registry scope
- [x] 2.7 Implement renderer mappings for Codex `mcp_servers`, Gemini/Qwen/Claude `mcpServers`, and OpenCode `mcp`

## 3. Runtime Config Integration

- [x] 3.1 Add bypass validation that rejects `mcpServers`, `mcp_servers`, and `mcp` in skill engine config assets
- [x] 3.2 Add bypass validation that rejects `mcpServers`, `mcp_servers`, and `mcp` in request-side runtime engine config overrides
- [x] 3.3 Merge governed MCP renderer output as a system-generated layer after skill defaults/runtime overrides and before enforced policy
- [x] 3.4 Preserve existing non-MCP runtime config composition behavior when no MCP entries resolve
- [x] 3.5 Ensure engine-specific composers consume rendered MCP config rather than parsing skill MCP declarations directly

## 4. Codex Per-Run Profile

- [x] 4.1 Create a per-run Codex profile when a Codex run resolves any declared MCP entry
- [x] 4.2 Ensure Codex start/resume commands select the per-run MCP profile
- [x] 4.3 Keep default Codex MCP behavior compatible with managed agent-home configuration when registry scope permits it
- [x] 4.4 Add terminal cleanup that attempts to remove the per-run Codex MCP profile without changing the run outcome on cleanup failure

## 5. Tests and Verification

- [x] 5.1 Add MCP registry schema validation tests, including rejected secret-bearing fields
- [x] 5.2 Add skill manifest validation tests for valid and invalid `mcp.required_servers`
- [x] 5.3 Add resolver tests for default/declared activation and engine filtering
- [x] 5.4 Add rejection tests for unknown, unauthorized, or engine-incompatible MCP references
- [x] 5.5 Add bypass rejection tests for direct MCP root keys in skill config and runtime overrides
- [x] 5.6 Add renderer mapping tests for Codex, Gemini, Qwen, Claude, and OpenCode
- [x] 5.7 Add composer integration tests proving governed MCP precedence and no-op behavior
- [x] 5.8 Add Codex per-run profile creation, command profile selection, and cleanup tests
- [x] 5.9 Run `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_mcp_*.py`
