## 1. OpenSpec and Contracts

- [x] 1.1 Validate `add-mcp-management-ui` OpenSpec artifacts with `openspec validate add-mcp-management-ui --strict`
- [x] 1.2 Update MCP registry schema to allow structured `auth.env` and `auth.headers` secret references while rejecting raw secret-bearing fields
- [x] 1.3 Add DATA_DIR runtime path configuration for mutable MCP registry and MCP secret store

## 2. Runtime Registry and Secret Store

- [x] 2.1 Implement runtime registry loading that prefers DATA_DIR registry and falls back to packaged assets when absent
- [x] 2.2 Implement atomic runtime registry writes with invalid JSON backup and empty-structure recovery
- [x] 2.3 Implement MCP secret store with atomic writes, masked/list behavior, upsert replacement, delete cleanup, and best-effort `0600`
- [x] 2.4 Extend MCP registry model parsing to include auth secret references without exposing raw secrets

## 3. Management API

- [x] 3.1 Add MCP management request/response models with masked auth views and raw-value write-only fields
- [x] 3.2 Add `GET /v1/management/mcp/servers`, `PUT /v1/management/mcp/servers/{server_id}`, and `DELETE /v1/management/mcp/servers/{server_id}`
- [x] 3.3 Validate upsert requests with registry schema, engine filtering, transport requirements, secret-preservation semantics, and no raw secret echo
- [x] 3.4 Delete server-associated secret refs when deleting an MCP server

## 4. Runtime Rendering Integration

- [x] 4.1 Resolve MCP secret references during renderer/composer execution
- [x] 4.2 Inject stdio auth as env variables and HTTP/SSE auth as headers for Codex, Gemini, Qwen, Claude, and OpenCode roots
- [x] 4.3 Preserve default/declared engine filtering, direct MCP root-key bypass rejection, and Codex per-run profile behavior

## 5. Engine Management UI

- [x] 5.1 Add MCP management card to `server/assets/templates/ui/engines.html` after Engine Auth and before Custom Providers
- [x] 5.2 Implement list/create/edit/delete interactions using existing fetch/status/error UI conventions
- [x] 5.3 Keep key inputs write-only in the UI: blank preserves existing values and refreshed state is masked/configured only

## 6. Tests and Verification

- [x] 6.1 Add schema and secret-store tests for auth refs, raw secret rejection, atomic writes, masked views, replacement, and cleanup
- [x] 6.2 Add management API tests for list/upsert/delete and no raw key echo
- [x] 6.3 Add resolver/renderer/composer tests for env/header secret injection across supported engines and existing policy regressions
- [x] 6.4 Add UI route/template tests that `/ui/engines` renders the MCP section
- [x] 6.5 Run `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit/test_mcp_*.py tests/unit/test_management_api.py tests/unit/test_ui_routes.py`
- [x] 6.6 Run `conda run --no-capture-output -n DataProcessing python -u -m mypy <changed server modules>`
- [x] 6.7 Run `conda run --no-capture-output -n DataProcessing python -u -m ruff check <changed files>`
