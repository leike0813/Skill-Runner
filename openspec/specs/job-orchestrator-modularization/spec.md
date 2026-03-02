# job-orchestrator-modularization Specification

## Purpose
TBD - created by archiving change refactor-job-orchestrator-god-object. Update Purpose after archive.
## Requirements
### Requirement: JobOrchestrator MUST act as a coordination layer
The system MUST constrain `JobOrchestrator` to lifecycle coordination and delegation, instead of embedding bundle, filesystem snapshot, audit, interaction lifecycle, and restart recovery implementations in a single class.

#### Scenario: Run execution delegates component responsibilities
- **WHEN** `JobOrchestrator.run_job` processes a run
- **THEN** it MUST delegate bundle, snapshot, audit, and interaction lifecycle operations to dedicated services

#### Scenario: Trust registration canonical path moves with lifecycle
- **WHEN** run-folder trust registration belongs to lifecycle execution
- **THEN** tests MUST assert the lifecycle-service call site
- **AND** the system MUST NOT move the logic back into `JobOrchestrator` only to satisfy legacy tests

### Requirement: Dedicated orchestration services MUST preserve run behavior
The system MUST provide dedicated orchestration services for bundle, filesystem snapshot, audit, interaction lifecycle, and restart recovery while preserving the existing run behavior and output semantics.

#### Scenario: Terminal outputs remain backward compatible
- **WHEN** a run reaches terminal state (`succeeded`/`failed`/`canceled`)
- **THEN** `status.json`, `result/result.json`, `.audit/*`, and `bundle/*` outputs MUST preserve current semantics and compatibility

### Requirement: Job control integration MUST expose stable bundle API with compatibility fallback
The system MUST expose `build_run_bundle(run_dir, debug)` on job-control integration points and MUST keep compatibility with legacy `_build_run_bundle` callers during migration.

#### Scenario: Runtime read facade can request bundle via stable API
- **WHEN** runtime observability requests a run bundle
- **THEN** it MUST call `build_run_bundle` when available and MUST fall back to `_build_run_bundle` to support legacy implementations

### Requirement: Interactive and recovery semantics MUST remain unchanged
The system MUST keep interactive waiting/reply/auto-decide timeout and restart recovery semantics unchanged after modularization.

#### Scenario: Interactive waiting and auto resume remain consistent
- **WHEN** an interactive run enters `waiting_user` and later receives user reply or timeout auto-decision
- **THEN** status transitions, reply dedup/idempotency behavior, and resume command semantics MUST stay consistent with current behavior

#### Scenario: Restart recovery remains compatible
- **WHEN** orchestrator starts and reconciles incomplete runs
- **THEN** waiting-preserve and failed-reconcile outcomes MUST remain consistent with current statechart-driven behavior

#### Scenario: Lifecycle extraction does not add compatibility shims
- **WHEN** `run_job`, `cancel_run`, or recovery flows execute through lifecycle services
- **THEN** behavior MUST stay compatible with the current public contract
- **AND** the fix MUST land in canonical service code paths
- **AND** the system MUST NOT add legacy wrapper shims to preserve stale tests
