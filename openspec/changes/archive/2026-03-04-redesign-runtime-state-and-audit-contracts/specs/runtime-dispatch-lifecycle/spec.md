## ADDED Requirements

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
