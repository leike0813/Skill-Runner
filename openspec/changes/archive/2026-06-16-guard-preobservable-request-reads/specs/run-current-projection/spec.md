## MODIFIED Requirements

### Requirement: Current projection reads MUST distinguish missing request from pre-observable request
The current-state read model MUST distinguish an unknown `request_id` from a known request that does not yet have an observable run.

#### Scenario: Pre-observable request has no current projection yet
- **GIVEN** a request record exists
- **AND** no current projection exists because no run has been bound
- **WHEN** the status API is read
- **THEN** the response MUST be a queued request projection
- **AND** it MUST expose `observability_ready=false`

#### Scenario: Bound run remains observable
- **GIVEN** a request record has a bound and resolvable run
- **WHEN** the status API is read
- **THEN** the response MUST expose `observability_ready=true`
