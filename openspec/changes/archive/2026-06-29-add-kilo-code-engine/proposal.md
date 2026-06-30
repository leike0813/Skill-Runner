## Why

Skill Runner currently supports several managed coding-agent engines, but Kilo Code is not available as a first-class engine. Kilo exposes a standardized non-interactive CLI, JSONL stdout events, XDG-isolated state, and a model-probe command, making it suitable for the existing profile-driven adapter architecture.

## What Changes

- Add `kilo` as a supported engine with a dedicated `server/engines/kilo/**` package.
- Support managed install/bootstrap for `@kilocode/cli` and cross-platform `kilo`/`kilocode` binaries.
- Execute Kilo through `kilo run --format json --auto`, including `--session` resume.
- Compose Kilo run configuration into `<workspace_root>/.kilo/kilo.jsonc` using the shared non-Codex config layering contract.
- Add a runtime model probe backed by `kilo models --verbose` with last-known-good cache and a minimal fallback model.
- Parse Kilo JSONL stdout success and error events, including auth-related JSONL errors whose process exit code may still be `0`.
- Expose Kilo in engine registry, management/status surfaces, UI metadata, skill manifest schemas, MCP engine enums, and harness skill injection.
- Defer interactive Kilo auth, Gateway BYOK management, third-party provider configuration, provider-aware auth registry, and credential import to later changes.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `engine-adapter-runtime-contract`: Add Kilo as a first-class profile-driven runtime adapter.
- `engine-runtime-config-layering`: Add Kilo `.kilo/kilo.jsonc` config layering and phase-1 provider-root restriction.
- `engine-command-profile-defaults`: Add Kilo command defaults for JSONL execution.
- `engine-status-cache-management`: Include Kilo in engine status cache and stable UI/API rows.
- `engine-upgrade-management`: Support managed installation and upgrades for `@kilocode/cli`.
- `local-deploy-bootstrap`: Bootstrap Kilo managed home and run-folder layout.
- `ui-engine-management`: Show Kilo in management UI and engine selection without auth actions.
- `external-runtime-harness-cli`: Add Kilo as a harness skill-injection target.
- `mcp-config-governance`: Allow governed MCP rendering for Kilo while rejecting user-authored Kilo `mcp` roots.
- `skill-package-validation-schema`: Allow skill manifests to target Kilo engine config.
- `engine-auth-strategy-policy`: Allow Kilo to declare phase-1 auth disabled/no-start semantics while retaining runtime auth-error detection.

## Impact

- Adds engine assets and code under `server/engines/kilo/**`.
- Updates engine registration, schema enums, management/bootstrap/status/UI integration, and focused unit tests.
- Does not introduce new public HTTP APIs or credential storage formats.
