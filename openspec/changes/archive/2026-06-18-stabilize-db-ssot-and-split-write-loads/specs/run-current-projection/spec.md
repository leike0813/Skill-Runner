# run-current-projection Delta

## MODIFIED Requirements

### Requirement: Current run state MUST come from DB projection/state
Request-bound status, list, detail, reply gating, cancel gating, and management projections MUST use DB state/projection rows as the current truth.

#### Scenario: State file disagrees with DB state
- **GIVEN** a request-bound run has DB state `succeeded`
- **AND** `.state/<namespace>/state.json` exists with status `running`
- **WHEN** status, list, detail, reply, or cancel reads current state
- **THEN** the response uses `succeeded`
- **AND** the file payload is ignored for state decisions.

#### Scenario: Request-bound state files are absent
- **GIVEN** a request-bound run has DB state and dispatch rows
- **WHEN** observability reads status or detail
- **THEN** it succeeds without `.state/<namespace>/state.json`
- **AND** it succeeds without `.state/<namespace>/dispatch.json`.
