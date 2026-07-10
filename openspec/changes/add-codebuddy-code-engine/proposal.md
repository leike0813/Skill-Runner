## Why

Skill Runner does not yet expose CodeBuddy Code as a first-class engine even though the investigated CLI provides headless stream output, exact session resume, project skills, structured output, and managed installation. The integration must preserve Skill Runner's isolation and audit contracts while routing CodeBuddy's China and global login environments independently.

## What Changes

- Add `codebuddy` as a profile-driven engine with managed install/upgrade, run-local workspace materialization, exact-session resume, structured output, MCP isolation, runtime parser semantics, and management UI support.
- Model CodeBuddy China and global entry points as the required virtual providers `codebuddy-cn` and `codebuddy-global`; a job's existing `provider_id` selects its credential, network environment, persistent CLI state, session lineage, and model catalog.
- Add an isolated SDK authentication worker and a provider-keyed local credential vault. Raw tokens never enter normal persistence, logs, audits, bundles, model probe evidence, or API responses.
- Add a provider-partitioned runtime model catalog derived from the installed CLI's help output together with CLI version, environment, collection time, and raw probe reference; do not add a pinned model manifest.
- Materialize `CODEBUDDY.md`, `.codebuddy/skills`, controlled settings, and a strict generated MCP config in each run workspace.
- Parse CodeBuddy stream JSON into existing Runtime/FCMP/RASP semantics, including malformed-stream recovery, repeated init events, structured output, process events, exact run handles, and terminal errors whose process exit code is `0`.
- Expose CodeBuddy installation, version, provider credential status, authentication actions, provider-filtered models, and credential removal through existing management surfaces plus one provider-credential deletion endpoint.
- Keep cache policy caller-controlled; CodeBuddy does not force `no_cache` or add credential identity to cache keys.
- Do not expose an inline CodeBuddy TUI in this release.

## Capabilities

### New Capabilities

- `engine-managed-credential-vault`: Provider-keyed durable engine credentials with atomic local storage, redacted status projections, expiry metadata, deletion, and process-only secret injection.

### Modified Capabilities

- `engine-adapter-runtime-contract`: Add CodeBuddy command, workspace, session, structured-output, parser, and terminal semantics.
- `engine-auth-strategy-policy`: Add the two CodeBuddy virtual providers and their startable browser authentication methods.
- `engine-auth-observability`: Add provider-scoped redaction, credential state, and runtime reauthorization semantics.
- `engine-command-profile-defaults`: Declare CodeBuddy headless start/resume defaults in its adapter profile.
- `engine-runtime-config-layering`: Define system-owned CodeBuddy project settings and provider-scoped persistent config directories.
- `engine-status-cache-management`: Add stable CodeBuddy status rows and provider catalog state.
- `engine-upgrade-management`: Manage `@tencent-ai/codebuddy-code` and its binary aliases.
- `external-runtime-harness-cli`: Inject skills into `.codebuddy/skills`.
- `interactive-job-api`: Require a CodeBuddy virtual provider on job creation and preserve it across auth/resume.
- `local-deploy-bootstrap`: Create CodeBuddy managed runtime directories and bootstrap assets.
- `management-api-surface`: Expose provider-qualified models, redacted credential state, and provider credential deletion.
- `mcp-config-governance`: Render strict system-generated CodeBuddy `mcpServers` configuration.
- `runtime-env-options`: Reserve CodeBuddy-managed credential and routing variables from request overrides.
- `skill-package-validation-schema`: Allow skills to target CodeBuddy.
- `ui-engine-management`: Add CodeBuddy status, install, provider authentication, credential removal, and provider-filtered model selection without inline TUI.

## Impact

- Adds `server/engines/codebuddy/**`, CodeBuddy parser/auth/model fixtures, and a detailed implementation plan under `artifacts/`.
- Updates machine-readable engine/profile/skill/MCP contracts, engine registries, model lifecycle, auth bootstrap, request validation, MCP rendering, management APIs, UI metadata/templates/locales, harness support, and documentation.
- Adds the pinned Python dependency `codebuddy-agent-sdk==0.3.205` and managed npm package metadata for `@tencent-ai/codebuddy-code`.
- Adds `DELETE /v1/management/engines/{engine}/auth/credentials/{provider_id}`. Existing job and auth-session request shapes are reused.
- Does not add FCMP/RASP event names or change the canonical session statechart.
