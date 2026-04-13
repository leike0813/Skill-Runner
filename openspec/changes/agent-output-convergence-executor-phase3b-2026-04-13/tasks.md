## 1. OpenSpec Change Artifacts

- [x] 1.1 Add proposal/design/tasks for the phase 3B convergence-executor slice.
- [x] 1.2 Add delta specs for `output-json-repair`, `interactive-run-lifecycle`, `interactive-engine-turn-protocol`, and `run-audit-contract`.

## 2. Runtime Implementation

- [x] 2.1 Add the orchestrator-side output convergence service and integrate attempt-level repair rounds into the lifecycle pipeline.
- [x] 2.2 Ensure repair is handle-gated, round-aware, and audited via `.audit/output_repair.<attempt>.jsonl`.
- [x] 2.3 Route interactive pending branches through the union schema and formal waiting-user projection.
- [x] 2.4 Remove `<ASK_USER_YAML>` from the formal interactive patch contract and main-path waiting classification.

## 3. Runtime Protocol Integration

- [x] 3.1 Emit repair orchestrator events and keep them out of FCMP translation.
- [x] 3.2 Update observability summaries so repair rounds are visible and distinguish deterministic parse vs schema outcomes.

## 4. Validation

- [x] 4.1 Add or update targeted unit tests for convergence, lifecycle, adapter round semantics, protocol, and observability.
- [x] 4.2 Run targeted pytest for the affected runtime surface.
- [x] 4.3 Run mypy for the new convergence service and touched orchestration/adapter files.
