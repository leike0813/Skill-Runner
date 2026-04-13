## Why

Phase 0A established the target JSON-only output contract in a spec-first guard slice, and phase 1 introduced run-scoped output schema materialization. However, the repository's main documentation and main spec surface still describe the older mixed regime: `<ASK_USER_YAML>` as an accepted control-plane protocol, interactive soft completion as a normative success path, and ask-user evidence as the primary waiting-user source.

This phase 0B slice aligns the repository-level SSOT expression with the target contract direction without changing runtime code or syncing main specs directly.

## What Changes

- Create an OpenSpec change that expresses the target updates through delta specs instead of directly editing `openspec/specs/*`.
- Update the core `docs/` protocol and lifecycle documents so they no longer present `<ASK_USER_YAML>` or soft completion as the target contract.
- Reframe interactive waiting semantics around the pending JSON branch (`__SKILL_DONE__ = false + message + ui_hints`).
- Reframe output-schema guidance around run-scoped materialized JSON Schema artifacts, with prompt-facing markdown as a derived projection.
- Mark legacy ask-user and soft-completion behavior as rollout/deprecation background only where historical context is still needed.

## Capabilities

### Modified Capabilities
- `interactive-engine-turn-protocol`
- `interactive-run-lifecycle`
- `interactive-decision-policy`
- `output-json-repair`
- `skill-patch-modular-injection`
- `interactive-job-api`

## Impact

- New OpenSpec change artifacts under `openspec/changes/agent-output-ssot-sync-phase0b-2026-04-12/`
- Direct documentation updates under `docs/`
- No runtime code, HTTP API, FCMP/RASP wire shape, or schema file changes in this slice
