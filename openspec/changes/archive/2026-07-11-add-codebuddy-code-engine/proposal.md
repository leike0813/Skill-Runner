## Why

Skill Runner does not yet expose CodeBuddy Code as a first-class engine even though the investigated CLI provides headless stream output, exact session resume, project skills, structured output, and managed installation. The integration must preserve Skill Runner's isolation and audit contracts while routing CodeBuddy's China and global login environments independently.

## What Changes

- Add `codebuddy` as a profile-driven engine with managed install/upgrade, run-local workspace materialization, exact-session resume, structured output, MCP isolation, runtime parser semantics, and management UI support.
- Model CodeBuddy China and global entry points as the required virtual providers `codebuddy-cn` and `codebuddy-global`; a job's existing `provider_id` selects its credential, network environment, persistent CLI state, session lineage, and provider-qualified static model entry.
- Add an isolated SDK authentication worker and a provider-keyed local credential vault. Raw tokens never enter normal persistence, logs, audits, bundles, or API responses.
- Manage CodeBuddy models through the same pinned static manifest mechanism as Codex. The manifest remains engine-local, contains provider-qualified entries for both virtual providers, and is the only CodeBuddy model source.
- Materialize `CODEBUDDY.md`, `.codebuddy/skills`, controlled settings, and a strict generated MCP config in each run workspace.
- Parse CodeBuddy stream JSON into existing Runtime/FCMP/RASP semantics, including malformed-stream recovery, repeated init events, structured output, process events, exact run handles, and terminal errors whose process exit code is `0`.
- Expose CodeBuddy installation, version, provider credential status, authentication actions, provider-filtered models, and credential removal through existing management surfaces plus one provider-credential deletion endpoint.
- Route missing, expired, and runtime-unauthorized CodeBuddy credentials through the existing waiting-auth lifecycle; successful browser authentication automatically requeues the attempt and preserves exact provider/session resume when available.
- Keep cache policy caller-controlled; CodeBuddy does not force `no_cache` or add credential identity to cache keys.
- Enable the existing inline TUI for CodeBuddy with an explicit authenticated provider, session-local enforced settings, managed credential environment, and an empty strict MCP source.
- Keep CodeBuddy job creation in the built-in `e2e_client`; the management UI remains limited to engine status, credentials, installation/upgrade, and existing shell controls.
- Complete Kilo's governed MCP integration by using the same native `mcp` configuration shape as OpenCode.
- Restore the managed bootstrap default to only `opencode,codex`; Claude Code, Qwen Code, Kilo Code, and CodeBuddy remain explicitly installable on demand. Gemini remains a deprecated sealed implementation and is not an install target.
- Gate Kilo runtime model probing on a fresh engine-status result that confirms the CLI is installed.

## Capabilities

### New Capabilities

- `engine-managed-credential-vault`: Provider-keyed durable engine credentials with atomic local storage, redacted status projections, expiry metadata, deletion, and process-only secret injection.
- `builtin-e2e-example-client`: Provider-first CodeBuddy job creation through the repository's existing example client.
- `kilo-model-catalog-refresh`: Installation-gated Kilo model discovery and refresh lifecycle.

### Modified Capabilities

- `engine-adapter-runtime-contract`: Add CodeBuddy command, workspace, session, structured-output, parser, and terminal semantics.
- `engine-auth-strategy-policy`: Add the two CodeBuddy virtual providers and their startable browser authentication methods.
- `engine-auth-observability`: Add provider-scoped redaction, credential state, and runtime reauthorization semantics.
- `engine-command-profile-defaults`: Declare CodeBuddy headless start/resume defaults in its adapter profile.
- `engine-runtime-config-layering`: Define system-owned CodeBuddy project settings and provider-scoped persistent config directories.
- `engine-status-cache-management`: Add stable CodeBuddy installation status rows without coupling status refresh to model discovery.
- `engine-upgrade-management`: Manage `@tencent-ai/codebuddy-code` and its binary aliases.
- `external-runtime-harness-cli`: Inject skills into `.codebuddy/skills`.
- `interactive-job-api`: Require a CodeBuddy virtual provider on job creation and preserve it across auth/resume.
- `local-deploy-bootstrap`: Create CodeBuddy managed runtime directories and bootstrap assets.
- `management-api-surface`: Expose provider-qualified models, redacted credential state, and provider credential deletion.
- `mcp-config-governance`: Render strict system-generated CodeBuddy `mcpServers` configuration.
- `runtime-env-options`: Reserve CodeBuddy-managed credential and routing variables from request overrides.
- `skill-package-validation-schema`: Allow skills to target CodeBuddy.
- `ui-engine-management`: Add CodeBuddy status, install, provider authentication, credential removal, provider-filtered model selection, and explicit-provider inline TUI controls without adding a job launcher.
- `ui-engine-inline-terminal`: Add provider-gated CodeBuddy TUI launch with session-local security configuration and strict MCP isolation.
- `mcp-config-governance`: Render Kilo MCP configuration with the same governed `mcp` contract as OpenCode and keep CodeBuddy TUI MCP empty and strict.
- `local-deploy-bootstrap`: Make `opencode,codex` the complete default install set, retain explicit on-demand installation for active supported engines, and reject deprecated Gemini as an install target.

## Impact

- Adds `server/engines/codebuddy/**`, including its model manifest, engine-local release-gate schema, credential-aware runtime/TUI launch logic, plus CodeBuddy parser/auth/model fixtures and a detailed implementation plan under `artifacts/`.
- Updates machine-readable engine/profile/skill/MCP contracts, engine registries, model lifecycle, auth bootstrap, request validation, MCP rendering, management APIs, UI metadata/templates/locales, harness support, and documentation.
- Updates the built-in `e2e_client` provider/model form behavior without adding management UI job routes.
- Adds the pinned Python dependency `codebuddy-agent-sdk==0.3.205` and managed npm package metadata for `@tencent-ai/codebuddy-code`.
- Adds `DELETE /v1/management/engines/{engine}/auth/credentials/{provider_id}` and an optional `provider_id` form field to the existing internal UI-shell start route. Existing public job and auth-session request shapes are reused.
- Does not add FCMP/RASP event names or change the canonical session statechart.
