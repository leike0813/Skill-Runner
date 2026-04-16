## 1. Stage 0 Guardrails

- [x] 1.1 Add change artifacts and stage-by-stage refactor requirements under `job-orchestrator-modularization`.
- [x] 1.2 Add façade guardrail tests that freeze stable `JobOrchestrator` entrypoints and `run_job` delegation through `RunJobLifecycleService`.

## 2. Stage 1 Run Attempt Preparation

- [x] 2.1 Introduce `RunAttemptPreparationService` and `RunAttemptContext` for request/attempt/skill/input/run-options preparation.
- [x] 2.2 Refactor `run_job_lifecycle_service.py` to consume `RunAttemptContext` for the preparation slice without changing external run behavior.
- [x] 2.3 Add focused unit tests for the preparation service and keep existing orchestration regressions green.

## 3. Future Stages

- [x] 3.1 Extract `RunAttemptExecutionService`.
- [x] 3.2 Extract `RunAttemptOutcomeService`.
- [x] 3.3 Extract projection and audit finalizers.
- [x] 3.4 Split `tests/unit/test_job_orchestrator.py` by orchestration responsibility and slim `JobOrchestrator`.

## 4. Validation

- [x] 4.1 Run targeted orchestration pytest coverage for façade, preparation, convergence, interaction, auth, protocol, and observability behavior.
- [x] 4.2 Run `mypy --follow-imports=skip server/services/orchestration`.
