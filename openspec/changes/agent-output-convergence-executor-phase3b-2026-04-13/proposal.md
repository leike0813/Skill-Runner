# Phase 3B: Output Convergence Executor

## Why

Phase 3A defined the repair governance model, but runtime behavior still spreads output
normalization across parser repair, schema validation, legacy ask-user waiting heuristics,
and result-file fallback. That fragmentation makes it hard to reason about ownership,
attempt-vs-round semantics, and audit completeness.

Phase 3B implements the orchestrator-side output convergence executor so each attempt
uses one handle-gated repair loop, with deterministic parse repair performed inside each
round and legacy `<ASK_USER_YAML>` removed from the formal waiting path.

## What Changes

- Add an orchestrator-side output convergence executor that owns attempt-level repair.
- Require a persisted session handle before any repair rerun is allowed.
- Apply repair to every attempt, including interactive non-final attempts.
- Fold deterministic parse repair into each repair loop iteration instead of repeating it
  again in downstream fallback logic.
- Promote interactive union-schema pending branches into the formal waiting-user source.
- Emit repair orchestrator events and write `.audit/output_repair.<attempt>.jsonl`.
- Remove `<ASK_USER_YAML>` from the formal interactive prompt contract and runtime
  main-path waiting classification.

## Scope

In scope:

- `run_output_convergence_service`
- lifecycle integration
- repair audit and repair events
- interactive prompt/protocol changes
- targeted tests and type checks

Out of scope:

- HTTP API changes
- FCMP/RASP public wire-shape changes
- new repair feature flags
- alternative no-session-handle restart flows
