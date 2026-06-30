## OpenSpec

- [x] Create proposal, design, delta specs, and task list for Kilo phase 1.
- [x] Validate the change with `openspec validate add-kilo-code-engine --strict`.

## Engine Package

- [x] Create `server/engines/kilo/**` package with adapter, config, schema, model, and auth-pattern assets.
- [x] Implement Kilo command builder, config composer, execution adapter, stream parser, and runtime model probe service.
- [x] Add Kilo adapter profile with profile-declared command, config, workspace, model catalog, managed CLI, and parser auth metadata.

## Central Registration

- [x] Add `kilo` to engine keys, engine exports, adapter registry, schema enums, and management/upgrade/status registrations.
- [x] Add Kilo bootstrap defaults and managed install metadata from profile.
- [x] Add Kilo to UI metadata, harness skill injection targets, and supported manifest/MCP engine lists.

## Phase-1 Auth Boundary

- [x] Add Kilo auth strategy disabled/no-start support without registering provider-aware auth or interactive auth flows.
- [x] Add runtime/parser auth detection for Kilo JSONL auth failures.

## Testing

- [x] Add/update unit tests for Kilo command/config/parser/model probe/registry/schema/management behavior.
- [x] Run focused pytest suite for adapter, schema, auth strategy, bootstrap, upgrade, and parser contracts.
