## MODIFIED Requirements

### Requirement: JobOrchestrator MUST delegate run lifecycle pipeline
Wave2 MUST move `run_job` lifecycle execution out of `JobOrchestrator` into a dedicated lifecycle service, while keeping `JobOrchestrator` as the stable coordination entrypoint.

#### Scenario: run_job delegates lifecycle execution
- **WHEN** `JobOrchestrator.run_job` is invoked
- **THEN** it MUST construct a lifecycle request and delegate execution to `RunJobLifecycleService` instead of embedding the full pipeline inline

### Requirement: Runtime behavior MUST remain backward compatible
Wave2 MUST preserve existing run semantics across interactive and non-interactive execution.

#### Scenario: terminal outputs remain unchanged
- **WHEN** a run reaches `succeeded`/`failed`/`canceled`
- **THEN** `status.json`, `result/result.json`, `.audit/*`, and `bundle/*` semantics MUST remain compatible with current behavior

#### Scenario: interactive lifecycle remains stable
- **WHEN** interactive run hits waiting/reply/auto-decide and recovery-related paths
- **THEN** status transitions, error code mapping, and event emission order MUST remain unchanged

### Requirement: Legacy test hooks MUST remain callable
Wave2 MUST preserve legacy helper/wrapper reachability used by existing tests and callers.

#### Scenario: orchestrator wrappers stay available
- **WHEN** existing tests call compatibility wrappers (for example `_build_run_bundle`, `_extract_pending_interaction*`, `_append_orchestrator_event`)
- **THEN** these entrypoints MUST continue to function without requiring wholesale test rewrites
