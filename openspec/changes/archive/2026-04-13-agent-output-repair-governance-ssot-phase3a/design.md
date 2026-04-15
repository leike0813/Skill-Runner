## Context

The repo already has the direction for JSON-only final/pending output contracts, but it still lacks a single governance model for output convergence. Today the story is fragmented:

- parser-level deterministic generic repair is described as a standalone success path
- schema repair is only described as bounded retries
- result-file fallback is documented as a separate recovery branch
- interactive waiting/completion exceptions still dominate the decision narrative

That fragmentation is exactly what phase 3B must avoid. This phase therefore defines a repair governance model before any repair-loop implementation lands.

Constraints:

- Do not change runtime code, adapter behavior, prompt patching, or lifecycle decisions.
- Do not emit new events yet; only define them in contracts and docs.
- Do not change FCMP/RASP public wire shapes.
- Do not switch `PendingInteraction` to pending-JSON sourcing in this slice.

## Goals / Non-Goals

**Goals**

- Formalize `attempt` and `internal_round` as distinct layers.
- Assign output convergence ownership to a single orchestrator-side executor.
- Unify deterministic parse repair, schema repair rounds, and legacy fallbacks into one governance pipeline.
- Reserve orchestrator repair events and audit assets so phase 3B can implement against a stable contract.
- Align machine contracts, OpenSpec deltas, and runtime docs to the same repair model.

**Non-Goals**

- Implement repair rounds or change `attempt_number` handling in code.
- Remove deterministic generic repair, result-file fallback, `<ASK_USER_YAML>`, or soft completion from runtime behavior.
- Change `PendingInteraction`, HTTP APIs, FCMP, or RASP.

## Decisions

### Decision 1: Model output convergence as `attempt + internal_round`

Each run turn keeps its existing outer `attempt_number`, but output convergence inside that attempt is modeled as ordered `internal_round`s.

Why:

- It makes repair retries observable without polluting attempt ownership, max-attempt policy, or user-visible lifecycle.
- It gives phase 3B a clear place to attach reuse of run handles and first-attempt audit suppression.

Rejected alternative:

- Treating each repair retry as a new attempt. That would blur orchestration ownership and distort current run history.

### Decision 2: Give output convergence a single orchestrator-side owner

The only component allowed to decide whether to continue deterministic repair, enter schema repair, or fall back to legacy lifecycle is the orchestrator-side output convergence executor.

Why:

- Parser and adapter logic can still produce candidate data, but they stop being separate governance authorities.
- This prevents drift between engine-specific adapters and lifecycle normalization code.

Rejected alternative:

- Leaving adapter/parser/local heuristics as peer decision-makers. That keeps the current scattered ownership problem.

### Decision 3: Define a unified repair pipeline

The target repair pipeline is:

1. deterministic parse repair
2. schema repair rounds
3. legacy lifecycle fallback
4. legacy result-file fallback
5. legacy interactive waiting/completion heuristics

Why:

- The repo already has these behaviors; phase 3A needs to place them in one ordered model instead of describing them as independent branches.

Rejected alternative:

- Only documenting schema repair rounds and ignoring existing fallback layers. That would keep the most failure-prone parts outside the formal model.

### Decision 4: Reserve dedicated orchestrator repair events now

Add repair event types to `runtime_contract.schema.json` even though no producer exists yet.

Why:

- Phase 3B needs a stable payload contract before implementation.
- These are internal orchestrator events only, so additive reservation does not change FCMP/RASP public protocol.

Rejected alternative:

- Waiting to add events until code exists. That would force behavior-first implementation and reintroduce SSOT drift.

### Decision 5: Document repair audit assets before emitting them

Define `.audit/output_repair.<attempt>.jsonl` as the target history file for convergence rounds, while marking it as phase-3B-target / not yet enforced in current runtime.

Why:

- The audit model is part of governance, not merely implementation detail.
- It lets docs and tests distinguish current append-only audit files from the future repair-round stream.

## Risks / Trade-offs

- **Schema reserved before producer exists**: acceptable because the new event types are internal and additive. Guard tests should validate schema shape, not presence in runtime output.
- **Docs may look ahead of implementation**: mitigate by explicitly labeling repair events, output-repair audit files, and executor ownership as target semantics for phase 3B.
- **Legacy behaviors remain in code**: mitigate by describing them as `legacy / current implementation only` rather than deleting them from the governance model.

## Migration Plan

1. Create the phase 3A change artifacts and delta specs.
2. Upgrade the machine-readable output invariants with the dual-layer model and ownership rules.
3. Add reserved orchestrator repair event types to the runtime contract schema.
4. Add guard tests for the new invariant fields and event payload validation.
5. Add a dedicated repair-governance SSOT doc and sync the existing runtime docs to it.

Rollback:

- Remove the new change directory, the new governance doc, the additive schema event types, and the guard-test additions.
- Restore the previous invariant file if downstream tooling assumes the old repair contract shape only.

## Open Questions

- None for this slice. Phase 3B will decide the exact runtime control flow and event emission call sites, but those decisions must conform to the model defined here.
