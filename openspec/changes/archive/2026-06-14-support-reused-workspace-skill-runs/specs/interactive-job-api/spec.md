## ADDED Requirements

### Requirement: Job create MUST accept workspace reuse runtime option
The job API SHALL accept `runtime_options.workspace` as the request-level workspace policy.

#### Scenario: Create request with workspace reuse
- **WHEN** a client creates a job with `runtime_options.workspace.mode="reuse"`
- **THEN** the request MUST include `runtime_options.workspace.request_id`
- **AND** the system MUST resolve that request id as the only public workspace reuse handle

#### Scenario: Create request with default workspace
- **WHEN** a client omits `runtime_options.workspace` or provides no reuse mode
- **THEN** the system creates a new physical workspace for the request

#### Scenario: Workflow workspace key is ignored
- **WHEN** a client provides `runtime_options.workflow_workspace`
- **THEN** the system MUST NOT treat it as a workspace reuse request

