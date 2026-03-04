## 1. Ordering Contract

- [x] 1.1 Add `docs/contracts/runtime_event_ordering_contract.yaml` and define streams, ordering domains, precedence rules, gating rules, projection rules, replay rules, buffer policies, and lifecycle normalization rules.
- [x] 1.2 Update `docs/contracts/session_fcmp_invariants.yaml` so state invariants align with canonical publish order, projection gating, replay consistency, and lifecycle normalization.
- [x] 1.3 Update protocol docs, schema docs, and sequence docs to describe canonical order, gate/buffer responsibilities, and single-track lifecycle semantics.

## 2. Specs and Schema Consolidation

- [x] 2.1 Refine OpenSpec deltas for `interactive-job-api`, `job-orchestrator-modularization`, `engine-adapter-runtime-contract`, and `runtime-event-ordering-contract` so they reflect gate-driven publication and lifecycle normalization.
- [x] 2.2 Remove redundant FCMP lifecycle event types from `server/models/runtime_event.py` and `server/assets/schemas/protocol/runtime_contract.schema.json`.
- [x] 2.3 Extend `conversation.state.changed` schema and factory helpers so terminal semantics live under `data.terminal`.

## 3. Ordering Gate Skeleton and Publishing Model

- [x] 3.1 Introduce `RuntimeEventCandidate`, `OrderingPrerequisite`, `OrderingDecision`, and gate/buffer skeleton types.
- [x] 3.2 Refine parser and orchestration publishing paths so parser-originated FCMP/RASP and lifecycle FCMP can be represented as candidates before publication.
- [x] 3.3 Keep live publisher, replay, and audit mirror paths aligned with canonical publish order and prevent batch/backfill from redefining active truth.

## 4. Lifecycle Event Normalization

- [x] 4.1 Remove `conversation.started`, `conversation.completed`, and `conversation.failed` from FCMP generation paths.
- [x] 4.2 Fold success/failure/cancel terminal semantics into terminal `conversation.state.changed.data.terminal`.
- [x] 4.3 Update UI/history/replay consumers so they only depend on canonical lifecycle FCMP and terminal projection gating.

## 5. Tests and Regression Guards

- [x] 5.1 Add contract tests for `runtime_event_ordering_contract.yaml`, lifecycle normalization, and terminal payload schema validation.
- [x] 5.2 Extend protocol and invariant tests to cover auth guidance before challenge publication, waiting-vs-terminal gating, and live/history order consistency.
- [x] 5.3 Add scenario regressions for `waiting_user` not exposing empty terminal results, auth prompt/challenge ordering, final assistant message before terminal projection, and batch/audit fallback not overriding live order.
