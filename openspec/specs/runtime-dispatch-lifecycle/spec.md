# runtime-dispatch-lifecycle Specification

## Purpose
TBD - created by archiving change simplify-temp-skill-lifecycle-and-complete-state-audit-cutover. Update Purpose after archive.
## Requirements
### Requirement: Dispatch Starts Only After Run-Local Materialization

Run dispatch MUST begin only after the run-local skill snapshot exists.

#### Scenario: Temp skill dispatch
- GIVEN a temp skill upload is accepted
- WHEN the run is created
- THEN the run-local skill snapshot is materialized before `dispatch_scheduled`

### Requirement: Dispatch Lifecycle Is Durable

The runtime MUST persist dispatch lifecycle progress separately from the top-level run status.

#### Scenario: dispatch phases are monotonic
- **WHEN** a run advances from create to execution
- **THEN** `.state/dispatch.json.phase` MUST advance in order:
  `created -> admitted -> dispatch_scheduled -> worker_claimed -> attempt_materializing`

### Requirement: Worker Claim Precedes Attempt Start

Attempt execution MUST NOT start before dispatch is claimed.

#### Scenario: attempt start requires worker claim
- **WHEN** `turn.started` is emitted for attempt 1
- **THEN** `.state/dispatch.json.phase` MUST already have reached `worker_claimed` or later

