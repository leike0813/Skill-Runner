# runtime-dispatch-state Delta

## MODIFIED Requirements

### Requirement: Dispatch state MUST be DB-backed for request-bound runs
Request-bound dispatch state MUST be stored and read from the `request_dispatch_state` DB table.

#### Scenario: Dispatch phase advances
- **WHEN** a request-bound dispatch phase advances
- **THEN** `request_dispatch_state` is updated in the run state DB
- **AND** the current projection is updated when the phase affects visible state
- **AND** no dispatch JSON file is required.

#### Scenario: Dispatch file is stale
- **GIVEN** `request_dispatch_state` has phase `attempt_materializing`
- **AND** `.state/<namespace>/dispatch.json` has phase `created`
- **WHEN** management or observability reads dispatch information
- **THEN** it uses the DB phase.
