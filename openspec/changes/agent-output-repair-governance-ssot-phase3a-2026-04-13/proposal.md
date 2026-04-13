## Why

The repository's current repair story is scattered across parser heuristics, schema validation notes, result-file fallback wording, and interactive waiting/completion exceptions. That makes phase 3B implementation risky because there is no single governance model for:

- `attempt` vs. internal repair rounds
- who owns output convergence decisions
- how deterministic parse repair, schema repair, and legacy fallbacks fit together
- which orchestrator events and audit assets must exist

Phase 3A fixes that drift first. It creates a dedicated repair-governance SSOT slice without changing runtime behavior.

## What Changes

- Add a new OpenSpec change that defines the target repair governance model for phase 3B.
- Upgrade the machine-readable output protocol invariants from guard-only repair wording to a formal `attempt + internal_round` model with single-executor ownership.
- Extend the runtime protocol schema with reserved orchestrator repair event types and their canonical payload shape.
- Add a dedicated repair-governance SSOT document and align the core runtime docs to the same model.
- Add guard tests that lock the new invariants and repair-event schema surface.

## Capabilities

### Modified Capabilities
- `output-json-repair`
- `interactive-run-lifecycle`
- `interactive-decision-policy`
- `interactive-engine-turn-protocol`
- `run-audit-contract`

## Impact

- New change artifacts under `openspec/changes/agent-output-repair-governance-ssot-phase3a-2026-04-13/`
- Additive schema changes in `server/contracts/schemas/runtime_contract.schema.json`
- Updated contract and documentation wording only; no runtime behavior changes in this slice
