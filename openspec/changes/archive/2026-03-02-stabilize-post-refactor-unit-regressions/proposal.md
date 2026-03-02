## Why

Recent refactors moved core execution, persistence, and engine management onto better architectural seams, but the implementation and test suite did not fully converge on those new seams. As a result, `pytest tests/unit` now fails broadly across async persistence, orchestration lifecycle, engine version caching, runtime import boundaries, and exception-handling guardrails.

## What Changes

- Repair async store and manager callsites in tests and remaining code paths so they consistently use `await`.
- Fix real post-refactor lifecycle regressions in the canonical orchestration path without adding compatibility wrappers or moving logic back into `JobOrchestrator`.
- Update model-registry tests to validate cache-backed engine version behavior instead of legacy probe-on-read behavior.
- Move the job-control port definition to a runtime-neutral module so runtime observability no longer imports `server.services.orchestration.*`.
- Narrow `management.py` boundary exception handling so broad-catch allowlist totals do not increase.
- Update isolated tests that still assert obsolete behavior:
  - E2E observation tests must reflect the current `agent_message` contract.
  - trust-folder invocation tests must assert the new lifecycle-service call site.

## Capabilities

### New Capabilities
- `post-refactor-compatibility-stability`: Stabilizes implementation and test behavior after async persistence, orchestration modularization, and engine status caching refactors.

### Modified Capabilities
- `job-orchestrator-modularization`: Clarify that lifecycle behavior must stay compatible after extraction without introducing legacy shims, and tests must follow canonical service boundaries.
- `exception-handling-hardening`: Require recently added management routes to narrow broad catches back within the allowlist baseline.
- `engine-management-domain-boundary`: Require runtime-facing modules to stop importing orchestration-owned ports directly.

## Impact

- Affected code:
  - `server/services/orchestration/*`
  - `server/runtime/observability/*`
  - `server/routers/management.py`
  - `server/services/engine_management/model_registry.py`
  - targeted unit tests under `tests/unit/*`
- Public APIs: no HTTP API or runtime schema changes.
- Internal module boundary: `JobControlPort` moves from orchestration-owned code to a runtime-neutral location.
