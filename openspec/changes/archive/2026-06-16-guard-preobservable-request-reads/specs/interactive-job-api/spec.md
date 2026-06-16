## MODIFIED Requirements

### Requirement: Job observability reads MUST tolerate pre-observable requests
After a job request has been accepted, the system MUST tolerate clients polling status, event, and chat endpoints before a run has been bound.

#### Scenario: Status for pre-observable request
- **GIVEN** a request exists
- **AND** no `run_id` has been bound yet
- **WHEN** the client calls `GET /v1/jobs/{request_id}`
- **THEN** the system returns `status=queued`
- **AND** `observability_ready=false`

#### Scenario: History for pre-observable request
- **GIVEN** a request exists
- **AND** no `run_id` has been bound yet
- **WHEN** the client calls `/events/history` or `/chat/history`
- **THEN** the system returns `200`
- **AND** the response contains no events
- **AND** `source=pre_observable`

#### Scenario: Missing request remains not found
- **GIVEN** no request exists for the supplied `request_id`
- **WHEN** the client calls a status, event, or chat endpoint
- **THEN** the system returns `404`
