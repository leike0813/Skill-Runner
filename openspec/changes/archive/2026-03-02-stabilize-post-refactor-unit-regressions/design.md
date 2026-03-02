## Context

The current unit failures are concentrated around three recent architectural shifts:

1. SQLite-backed stores and some managers are now async.
2. `run_job` lifecycle logic moved out of `JobOrchestrator`.
3. Engine versions now come from a persisted cache instead of probe-on-read behavior.

The intended architecture is still correct. The regression surface comes from code and tests that still assume the old calling style or old ownership boundary.

## Goals / Non-Goals

**Goals**
- Restore `pytest tests/unit` to green without reversing recent architectural decisions.
- Keep orchestration behavior compatible while preserving the thin-orchestrator direction.
- Re-align tests to current async and cache-backed semantics.
- Re-establish exception and import-boundary guardrails.

**Non-Goals**
- Do not reintroduce synchronous wrappers around async stores.
- Do not add legacy compatibility shims to `JobOrchestrator`.
- Do not restore probe-on-read engine version behavior.
- Do not change HTTP APIs, runtime schema, or statechart semantics.

## Decisions

### 1) Async migration remains canonical
- Decision: Fix tests and any remaining callsites to use async semantics directly.
- Rationale: The stores and managers were intentionally migrated to async; undoing that would recreate blocking behavior and duplicate interfaces.

### 2) Orchestration regressions are fixed in canonical services, not wrappers
- Decision: Any real behavior regression will be fixed in `run_job_lifecycle_service.py`, `run_recovery_service.py`, or the current `JobOrchestrator` public flow. No new compatibility wrapper or shim will be added.
- Rationale: Wrapper-only fixes would add technical debt and preserve stale injection paths instead of aligning tests with the current design.

### 3) Engine version reads remain cache-backed
- Decision: `model_registry` tests will patch `engine_status_cache_service`, not legacy version-detection internals.
- Rationale: The engine-management change explicitly moved version reads to `data/agent_status.json` and background refresh triggers.

### 4) Runtime-facing job-control port becomes runtime-neutral
- Decision: Move `JobControlPort` to `server/runtime/observability/job_control_port.py` and update both runtime and orchestration wiring to use it.
- Rationale: Runtime modules must not depend on orchestration-owned ports.

### 5) Management route exception handling must shrink
- Decision: Remove or narrow broad catches in `management.py` to explicit exception families:
  - `SystemSettingsValidationError`
  - `DataResetBusyError`
  - `ValueError`
  - `RuntimeError`
  - `OSError`
- Rationale: The broad-exception guard exists to prevent silent boundary expansion. These routes currently exceed the allowed baseline.

### 6) E2E observation tests follow current behavior, not the retired filter
- Decision: Update the E2E observation unit test to reflect the current rule that `agent_message` goes into chat bubbles without last-message filtering.
- Rationale: The template behavior changed intentionally; the test is stale.

## Risks / Trade-offs

- [Risk] Some failures that look like behavior regressions are actually test misuse of async APIs.
  - Mitigation: Fix the test preconditions first and only change production code where failures persist.
- [Risk] Moving `JobControlPort` could break runtime-observability wiring.
  - Mitigation: Update all imports in one pass and re-run the boundary and observability tests immediately.
- [Risk] Narrowing broad catches too aggressively could change HTTP 500 mapping.
  - Mitigation: Keep explicit mappings for known boundary exceptions and let FastAPI handle truly unexpected errors.

## Implementation Plan

1. Add OpenSpec artifacts for this stabilization change.
2. Update async-heavy unit tests to await stores and managers directly.
3. Re-run orchestration-focused tests and fix any remaining real behavior regressions in canonical lifecycle code.
4. Update model-registry tests to patch cache-backed engine version lookups.
5. Move `JobControlPort` into runtime-neutral code and remove orchestration import leakage.
6. Narrow `management.py` broad catches back within the allowlist.
7. Update isolated stale tests (`e2e` observation and trust-folder invocation path).
8. Run targeted suites, then `pytest tests/unit`, then mypy.

## Open Questions

- None. This change is decision-complete and intentionally avoids compatibility-shim tradeoffs.
