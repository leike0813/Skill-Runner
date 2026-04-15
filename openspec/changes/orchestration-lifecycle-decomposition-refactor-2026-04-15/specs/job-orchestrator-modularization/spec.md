## MODIFIED Requirements

### Requirement: JobOrchestrator MUST act as a coordination layer
The system MUST constrain `JobOrchestrator` to stable lifecycle coordination and delegation instead of letting new lifecycle decomposition work reintroduce business logic into the façade.

#### Scenario: stable orchestration entrypoints remain available during staged refactor
- **WHEN** lifecycle responsibilities are extracted into dedicated orchestration services
- **THEN** `JobOrchestrator` MUST keep stable entrypoints for `run_job`, `cancel_run`, and `recover_incomplete_runs_on_startup`
- **AND** `run_job` MUST continue to delegate through `RunJobLifecycleService`

## ADDED Requirements

### Requirement: Lifecycle decomposition MUST proceed through staged TDD guardrails
The system MUST decompose run lifecycle orchestration through staged, test-guarded refactor slices instead of a one-shot rewrite.

#### Scenario: stage introduces a new orchestration slice
- **WHEN** a lifecycle slice such as preparation, execution, outcome, or finalization is extracted
- **THEN** the stage MUST land dedicated guardrail or unit tests before or alongside the implementation move
- **AND** the stage MUST preserve the existing external run behavior

### Requirement: Run-attempt preparation MUST be extracted behind a typed context
The system MUST isolate run-attempt preparation behind a dedicated service that returns a typed preparation context for later lifecycle stages.

#### Scenario: lifecycle prepares a run attempt
- **WHEN** `RunJobLifecycleService` begins processing a run attempt
- **THEN** it MUST delegate request/attempt/skill/input/run-options preparation to `RunAttemptPreparationService`
- **AND** the service MUST return a `RunAttemptContext`
- **AND** later lifecycle steps MUST consume that context instead of recomputing the same preparation fields ad hoc
