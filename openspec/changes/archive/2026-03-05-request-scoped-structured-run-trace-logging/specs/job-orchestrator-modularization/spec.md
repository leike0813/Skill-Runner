## ADDED Requirements

### Requirement: Orchestration MUST emit request-scoped structured trace events

Runtime orchestration MUST emit stable structured trace logs for upload, lifecycle, interaction/auth, and recovery critical transitions. Critical transitions MUST carry `request_id` and stable event code semantics.

#### Scenario: upload failure can be traced by request_id
- **WHEN** `POST /v1/jobs/{request_id}/upload` fails at any critical phase
- **THEN** backend MUST emit `upload.failed`
- **AND** the event MUST include `request_id`, `phase`, `outcome=error`, and normalized error metadata

#### Scenario: run lifecycle slot handling remains traceable
- **WHEN** orchestration acquires and later releases a runtime slot
- **THEN** backend MUST emit `run.lifecycle.slot_acquired` and `run.lifecycle.slot_released`
- **AND** both events MUST be attributable to the same `run_id`

### Requirement: Recovery redrive decisions MUST be traceable

Recovery service MUST emit structured trace events for resume redrive decisions and orphan reconciliation.

#### Scenario: missing run_dir redrive is reconciled with trace
- **WHEN** queued redrive finds missing run directory
- **THEN** backend MUST emit a reconciliation trace event
- **AND** the event MUST carry `request_id`, `run_id`, and a stable error code for missing runtime assets
