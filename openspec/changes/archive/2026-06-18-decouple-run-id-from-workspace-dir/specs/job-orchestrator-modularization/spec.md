# job-orchestrator-modularization Delta

## MODIFIED Requirements

### Requirement: Orchestration MUST execute in the physical workspace
The job lifecycle MUST execute adapters with the persisted `workspace_dir` as cwd for request-bound runs.

#### Scenario: Background task receives logical run id
- **WHEN** a queued background task starts with only `run_id`
- **THEN** lifecycle resolves the request record by run id
- **AND** uses the persisted `workspace_dir` as the adapter cwd
- **AND** only falls back to `data/runs/<run_id>` for legacy no-layout records.

#### Scenario: Recovery uses workspace layout
- **WHEN** startup recovery, resume redrive, auth recovery, or interaction recovery updates run files
- **THEN** it resolves the persisted layout first
- **AND** writes state and audit files under the physical workspace namespace.
