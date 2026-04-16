# Proposal

## Why

Two repair-related regressions are now coupled:

1. Codex compat structured output is being validated against the runner canonical schema before it is canonicalized back into runner form. This causes valid `__SKILL_DONE__ = true` finals to fail the interactive union contract and enter repair incorrectly.
2. Repair-family chat visibility has drifted between the shared chat model, the management UI, and the e2e frontend. Superseded finals are effectively hidden instead of folded, and repair generations can be merged into one unstable bubble.

## What Changes

- Canonicalize Codex compat structured output payloads before branch resolution, schema validation, repair decisions, and outcome projection.
- Keep `target_output_schema.codex_compatible.json` as an engine-facing contract only; orchestrator logic uses canonical runner payloads.
- Align the shared chat model and management UI to the current e2e bubble semantics.
- Materialize superseded finals as inline folded revisions instead of removing them outright.
- Partition repair chains into stable family generations so later assistant messages are not folded into earlier repaired finals.

## Impact

- Valid Codex interactive finals can end a turn without being forced into repair.
- Shared chat rendering becomes stable across management UI and e2e observation.
- Public protocol surface stays unchanged: `assistant.message.superseded` / `assistant_revision` remain the only repair-visibility signals.
