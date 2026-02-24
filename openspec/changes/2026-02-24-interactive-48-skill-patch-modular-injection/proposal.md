## Why

Current skill patch behavior is partially hardcoded and partially file-backed, with injection rules scattered across adapters and harness paths. This creates drift risk and makes it hard to reason about which instructions are injected under each execution scenario.

We need one modular pipeline that:

1. Uses `server/assets/templates` as the single instruction source.
2. Applies fixed/conditional/mode-specific patches deterministically.
3. Reuses the same patching behavior in both `server` adapters and `agent_harness`.

## Dependencies

- Depends on `interactive-45-fcmp-single-stream-event-architecture` for stable interactive mode semantics.
- Depends on `interactive-46-event-command-schema-contract` and `interactive-47-session-invariants-property-model-tests` for downstream protocol/state consistency context.

## What Changes

1. Refactor `SkillPatcher` to a modular patch plan pipeline.
2. Add dynamic output schema patch generation from `output.schema.json`.
3. Move all runtime injection content to template-driven modules.
4. Remove legacy completion contract file path dependency.
5. Align `agent_harness` skill injection with the same patching path as server adapters.

## Capabilities

### Modified
- `interactive-engine-turn-protocol`
- `ephemeral-skill-upload-and-run`

### Added
- `skill-patch-modular-injection`

## Impact

- Server: `server/services/skill_patcher.py`, adapters.
- Harness: `agent_harness/skill_injection.py`.
- Templates: `server/assets/templates/*.md` become canonical source.
- Tests: skill patch pipeline/schema tests + adapter/harness updates.
