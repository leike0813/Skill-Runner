## 1. Stage 0 SSOT Guardrails

- [x] 1.1 Add change artifacts and the `runtime-turn-failure-governance` delta spec.
- [x] 1.2 Update runtime protocol schema, invariants, and docs for `agent.turn_failed` and diagnostic error-row governance.

## 2. Stage 1 Codex Semantic Failure Loop

- [x] 2.1 Teach the Codex parser to surface semantic turn failure and structured engine-error diagnostics while preserving raw evidence.
- [x] 2.2 Emit `agent.turn_failed` from runtime protocol/live publishing and keep it mutually exclusive with `agent.turn_complete`.
- [x] 2.3 Prefer semantic turn-failure message in terminal error summarization, result projection, and chat replay failure notice.

## 3. Validation

- [x] 3.1 Add/update targeted tests for protocol, parser, observability, outcome summarization, and chat replay derivation.
- [x] 3.2 Run targeted `pytest` and `mypy --follow-imports=skip server/runtime server/services/orchestration`.
