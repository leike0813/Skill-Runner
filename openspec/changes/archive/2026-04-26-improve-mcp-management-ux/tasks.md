## 1. OpenSpec Verification

- [x] 1.1 Validate `improve-mcp-management-ux` artifacts with `openspec validate improve-mcp-management-ux --strict`

## 2. MCP UI Structure

- [x] 2.1 Replace the raw MCP form with guided add/edit controls, native JSON import entry, advanced mode, and preview/status areas
- [x] 2.2 Replace comma/pipe auth syntax with structured inputs for args, env auth, and header auth
- [x] 2.3 Add scan-friendly list summaries for connection, enablement, engines, auth, and Claude agent-home default state

## 3. MCP UI Behavior

- [x] 3.1 Implement canonical browser form state shared by guided mode, advanced mode, edit actions, and import preview
- [x] 3.2 Implement typed auth compilation for no auth, Bearer token, API key header, custom header, and env token
- [x] 3.3 Implement native MCP JSON parsing for common roots and single-server objects with validation errors for unsupported shapes
- [x] 3.4 Preserve existing CRUD calls and write-only key semantics when building PUT payloads

## 4. Tests and Verification

- [x] 4.1 Update UI route/template tests for guided controls, typed auth controls, JSON import entry, advanced mode, and key-preservation hint
- [x] 4.2 Add regression assertion that the pipe-delimited auth instruction is removed
- [x] 4.3 Run targeted pytest suite for MCP governance, management API, and UI routes
- [x] 4.4 Run ruff on changed UI/test files
