## Why

Engine config schemas lag behind current upstream CLI contracts, causing valid modern config to be warned about or rejected. Gemini also no longer meets the maintenance bar for active execution and should be sealed like iFlow instead of continuing to appear in new-run and management surfaces.

## What Changes

- Refresh active engine config schemas for `codex`, `claude`, `opencode`, and `qwen` from current official/upstream references.
- Soft-deprecate Gemini: remove it from active execution, management, model, auth, install/upgrade, and skill engine-selection paths.
- Preserve `server/engines/gemini/` and read-only historical `.gemini` workspace inspection.
- Update docs and tests so Gemini is documented as legacy/deprecated rather than supported.

## Capabilities

### New Capabilities
- `gemini-engine-deprecation`: Sealed, read-only treatment for Gemini after removal from active engine surfaces.

### Modified Capabilities
- `engine-runtime-config-layering`: Active engine schema validation and layering apply only to maintained engines.
- `engine-adapter-runtime-contract`: Active adapter registration excludes Gemini while legacy files remain readable.
- `management-api-surface`: Engine lists, model lists, and UI/management selectors exclude Gemini.
- `engine-upgrade-management`: Install/upgrade tasks do not include Gemini.
- `skill-package-validation-schema`: Skill engine declarations reject Gemini for new packages/runs.
- `mcp-config-governance`: MCP active engine scopes reject Gemini.

## Impact

- Affects engine registries, adapter profile validation, model/auth/upgrade management, skill package validation, MCP registry schema, docs, and related tests.
- New run requests using `engine=gemini` become unsupported.
- Historical Gemini run files remain inspectable through generic read-only file browsing.
