## 1. Spec and Contract Updates

- [x] 1.1 Update `interactive-engine-turn-protocol` delta spec: remove mandatory ask_user gate and define dual-track interactive completion.
- [x] 1.2 Update `interactive-run-lifecycle` delta spec: codify mode-aware completion (`interactive` strong+soft dual-track, `auto` output-validity-first).
- [x] 1.3 Update `interactive-job-api` delta spec: pending is backend-owned baseline; `kind` remains compatibility/advisory.
- [x] 1.4 Update `interactive-decision-policy` delta spec: remove requirement that interactive patch must force ask_user structure.
- [x] 1.5 Update `run-observability-ui` and `builtin-e2e-example-client` delta specs: pending/reply driven by status+pending/protocol, not assistant JSON parsing.
- [x] 1.6 Add `skill-package-validation-schema` delta spec: `runner.json.max_attempt` optional integer (`>=1`) for interactive attempt bound.

## 2. Backend Lifecycle Refactor

- [x] 2.1 Refactor `job_orchestrator` interactive gate: evaluate strong evidence (done marker) and soft evidence (schema-valid output).
- [x] 2.2 Refactor `job_orchestrator` auto gate: allow success without done marker when output validates.
- [x] 2.3 Ensure done marker stripping before output validation for both modes.
- [x] 2.4 Ensure malformed ask_user payload cannot become output validation failure root cause.
- [x] 2.5 Normalize pending payload generation from backend baseline; optional ask_user parse only enriches metadata.
- [x] 2.5.1 Support non-JSON ask_user hint envelope (YAML) parsing from assistant stream for optional enrichment.
- [x] 2.5.2 Ensure ask_user hints (including YAML form) remain enrichment-only and are never used as lifecycle control predicates.
- [x] 2.6 Add `max_attempt` enforcement for interactive mode (`attempt_number >= max_attempt` and no completion evidence => fail with stable error code).
- [x] 2.7 Emit stable diagnostics:
  - warning `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`
  - error `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`
- [x] 2.8 Unify done-marker stream detection semantics across runtime gating and audit classification, including escaped NDJSON marker form.

## 3. Prompt Patch and Protocol Translation

- [x] 3.1 Update `skill_patcher` interactive mode text: remove mandatory structured ask_user requirement.
- [x] 3.1.1 Update `skill_patcher` interactive mode text: if providing ask_user hints, prefer YAML block (non-JSON).
- [x] 3.2 Keep done-marker contract and interactive "do not emit marker before completion" rule.
- [x] 3.3 Update protocol translation path to rely on persisted pending state for `user.input.required`.
- [x] 3.4 Ensure protocol emits:
  - `conversation.completed` with warning diagnostics for soft-completion;
  - `conversation.failed` with `INTERACTIVE_MAX_ATTEMPT_EXCEEDED` on attempt exhaustion.

## 4. UI / E2E Client Alignment

- [x] 4.1 Update management run observe page to avoid semantic dependence on `kind`.
- [x] 4.2 Update e2e run observe page to avoid semantic dependence on `kind` and assistant-side ask_user blocks.
- [x] 4.3 Ensure conversation rendering does not require assistant text to carry structured ask_user JSON.

## 5. Tests and Docs

- [x] 5.1 Update orchestrator unit tests for strong/soft/max-attempt gate behavior.
- [x] 5.2 Add regression test: malformed ask_user payload does not fail output validation path.
- [x] 5.2.1 Add regression test: YAML ask_user hints can be parsed into pending enrichment when run enters waiting_user.
- [x] 5.3 Update protocol/UI integration tests for waiting_user and reply flow under dual-track interactive gate.
- [x] 5.4 Run full unit test suite and fix regressions.
- [x] 5.5 Update `docs/runtime_stream_protocol.md`, `docs/api_reference.md`, and `docs/dev_guide.md`.
- [x] 5.6 Run OpenSpec validation and keep change in apply-ready state.
- [x] 5.7 Add regression test: escaped done marker in NDJSON string payload is recognized as completion evidence.
- [x] 5.8 Add regression test: marker detected + invalid output must fail and MUST NOT degrade to `waiting_user`.
