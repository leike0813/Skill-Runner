## Why

Kilo Code phase 1 adds execution, config composition, model probing, and parser support, but it intentionally leaves auth disabled and blocks native provider configuration. To make Kilo a complete engine, Skill Runner needs provider-aware auth for Kilo Gateway and the same third-party provider semantics already used by OpenCode.

## What Changes

- Promote `kilo` from auth-disabled phase-1 behavior to a provider-aware engine.
- Add Kilo Gateway auth as `provider_id=kilo` using the official device auth `oauth_proxy` flow.
- Reuse OpenCode provider-aware auth/config behavior for non-Gateway Kilo providers instead of defining a separate Kilo provider system.
- Open Kilo `kilo_config.provider` while keeping user-authored `mcp` roots governed-only.
- Preserve Kilo runtime-probe model IDs and provider IDs by enabling multi-provider model semantics.
- Expose Kilo provider-aware auth capabilities in management/UI surfaces without adding a separate Kilo provider CRUD surface.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `engine-auth-strategy-policy`: Kilo becomes a provider-aware auth engine with Gateway and OpenCode-compatible third-party providers.
- `auth-session-governance`: Kilo Gateway auth sessions use managed `oauth_proxy` lifecycle and provider-scoped mutual exclusion.
- `engine-auth-observability`: Kilo auth errors and session summaries must be redacted and observable.
- `ui-engine-management`: Kilo auth UI exposes Gateway and third-party provider choices through existing provider-aware flows.
- `engine-runtime-config-layering`: Kilo config allows `provider` roots while retaining governed MCP ownership.
- `models-module-boundary`: Kilo model catalog preserves provider-aware model identity and runtime model strings.

## Impact

- Adds Kilo auth modules under `server/engines/kilo/auth/**`.
- Updates auth strategy schema/config, provider-aware registry, auth bootstrap, Kilo config composer/profile, model handling tests, and UI/management capability tests.
- No new public HTTP API shape is introduced; existing provider-aware auth/session APIs gain Kilo provider records.
- No dependency installation or CLI delegated Gateway auth is required.
