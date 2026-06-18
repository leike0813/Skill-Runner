# run-file-contract Delta

## MODIFIED Requirements

### Requirement: State files MUST NOT be current request-bound artifacts
New request-bound runs MUST NOT rely on `.state/<namespace>/state.json` or `.state/<namespace>/dispatch.json` as current runner-owned state artifacts.

#### Scenario: Request-bound lifecycle writes state
- **WHEN** a request-bound run transitions state or dispatch phase
- **THEN** the backend writes `request_run_state`, `request_current_projection`, and/or `request_dispatch_state`
- **AND** it does not create `.state/<namespace>/state.json`
- **AND** it does not create `.state/<namespace>/dispatch.json`.

#### Scenario: Legacy state files exist
- **GIVEN** legacy `.state` files exist in a workspace
- **WHEN** a request-bound API reads current state
- **THEN** those files are treated as diagnostic/legacy data only.
