## Why

`server/services/orchestration/run_job_lifecycle_service.py` currently centralizes too many lifecycle responsibilities inside one `_RunJobLifecyclePipeline.run_job` method, while `server/services/orchestration/job_orchestrator.py` still carries a broad helper surface that makes the orchestrator hard to reason about, patch, and evolve safely.

This is core infrastructure. A one-shot rewrite would carry unacceptable regression risk for run execution, waiting/auth flows, repair/convergence, audit side effects, and recovery semantics. The refactor therefore needs to proceed in small, test-guarded slices.

## What Changes

- Introduce a staged refactor plan under the existing `job-orchestrator-modularization` capability.
- Add guardrail tests that freeze the stable `JobOrchestrator` façade and `run_job` delegation path.
- Start the first extraction slice by moving run-attempt preparation logic into a dedicated `RunAttemptPreparationService` that returns a typed `RunAttemptContext`.
- Keep `run_job`, `cancel_run`, and `recover_incomplete_runs_on_startup` behavior unchanged while the internals are decomposed.

## Capabilities

### Modified Capabilities
- `job-orchestrator-modularization`: orchestration lifecycle decomposition now proceeds through staged TDD loops, beginning with façade guardrails and dedicated run-attempt preparation extraction.

## Impact

- Affected code: orchestration lifecycle services, `JobOrchestrator` dependency wiring, and run-attempt preparation flow.
- Affected tests: new façade/preparation tests plus existing orchestration regression coverage.
- Affected docs/specs: `job-orchestrator-modularization` delta spec and change tasks/design.
