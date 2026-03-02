## MODIFIED Requirements

### Requirement: Interactive and recovery semantics MUST remain unchanged
The system MUST keep interactive waiting/reply/auto-decide timeout and restart recovery semantics unchanged after modularization.

#### Scenario: Lifecycle extraction does not add compatibility shims
- **WHEN** `run_job`, `cancel_run`, or recovery flows execute through lifecycle services
- **THEN** behavior MUST stay compatible with the current public contract
- **AND** the fix MUST land in canonical service code paths
- **AND** the system MUST NOT add legacy wrapper shims to preserve stale tests

### Requirement: JobOrchestrator MUST act as a coordination layer
The system MUST constrain `JobOrchestrator` to lifecycle coordination and delegation.

#### Scenario: Trust registration canonical path moves with lifecycle
- **WHEN** run-folder trust registration belongs to lifecycle execution
- **THEN** tests MUST assert the lifecycle-service call site
- **AND** the system MUST NOT move the logic back into `JobOrchestrator` only to satisfy legacy tests
