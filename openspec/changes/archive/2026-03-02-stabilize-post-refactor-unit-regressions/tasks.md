## 1. OpenSpec Artifacts

- [x] 1.1 Create `proposal.md`
- [x] 1.2 Create `design.md`
- [x] 1.3 Create `specs/post-refactor-compatibility-stability/spec.md`
- [x] 1.4 Create delta specs for:
  - `job-orchestrator-modularization`
  - `exception-handling-hardening`
  - `engine-management-domain-boundary`

## 2. Async Callchain Alignment

- [x] 2.1 Update `tests/unit/test_job_orchestrator.py` to await async store methods and align patch points with canonical dependencies
- [x] 2.2 Update `tests/unit/test_runs_router_cache.py` to await async request/run store methods
- [x] 2.3 Update `tests/unit/test_run_cleanup_manager.py` to use async helpers and await cleanup manager methods
- [x] 2.4 Update `tests/unit/test_skill_package_manager.py` to await async manager and store methods

## 3. Canonical Orchestration Behavior Fixes

- [x] 3.1 Re-run orchestration-focused tests after async test updates
- [x] 3.2 Fix any remaining `cancel_requested` / cancel / recovery regressions directly in canonical lifecycle code
- [x] 3.3 Ensure no compatibility wrappers or legacy shims are introduced

## 4. Engine Cache Semantics and Boundary Repairs

- [x] 4.1 Update `tests/unit/test_model_registry.py` to patch cache-backed version reads
- [x] 4.2 Add `server/runtime/observability/job_control_port.py`
- [x] 4.3 Update runtime/orchestration imports to use the runtime-neutral port definition
- [x] 4.4 Remove `server/services/orchestration/orchestrator_ports.py` after import migration is complete

## 5. Exception and Isolated Test Cleanup

- [x] 5.1 Narrow broad catches in `server/routers/management.py`
- [x] 5.2 Update `tests/unit/test_trust_folder_strategy_invocation_paths.py` to assert the lifecycle-service trust call site
- [x] 5.3 Update `tests/unit/test_e2e_completion_hidden_and_summary_single_source.py` to reflect current `agent_message` behavior

## 6. Verification

- [x] 6.1 Run targeted orchestration/cache suites
- [x] 6.2 Run `tests/unit/test_no_unapproved_broad_exception.py`
- [x] 6.3 Run `tests/unit/test_runtime_no_orchestration_imports.py`
- [x] 6.4 Run `tests/unit/test_run_observability.py`
- [x] 6.5 Run `conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit`
- [x] 6.6 Run mypy for modified production modules
