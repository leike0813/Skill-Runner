# run-current-projection Delta

## MODIFIED Requirements

### Requirement: current projection MUST be the single source of truth for non-terminal state
The backend MUST persist and read current state from the request-owned state path for request-bound runs with layout metadata.

#### Scenario: Run list and detail prefer namespaced state
- **GIVEN** a request-bound run has `.state/<namespace>/state.json`
- **AND** a stale root `.state/state.json` also exists
- **WHEN** list, detail, status, log-tail polling, cancel, or management diagnostics read current status
- **THEN** the namespaced state file is preferred
- **AND** stale root state cannot override the current request-bound status.

#### Scenario: Terminal result does not overwrite non-terminal current truth
- **WHEN** a request-bound run reaches terminal state
- **THEN** `.state/<namespace>/state.json` carries terminal current status
- **AND** `result/<namespace>/result.json` carries terminal result payload
- **AND** readers do not infer current status from a stale root state file.

### Requirement: Run projections MUST expose workspace diagnostics
Run projections SHALL expose the actual workspace and runner-owned paths used by the request-bound run.

#### Scenario: Diagnostics match layout-backed files
- **WHEN** a client reads request status or management detail for a namespaced run
- **THEN** `workspaceDir`, `resultJsonPath`, and `inputManifestPath` refer to the same namespace-backed layout
- **AND** diagnostics do not point to legacy root files unless no layout metadata exists.

## ADDED Requirements

### Requirement: Layout-backed status updates MUST not bypass projection service
Request-bound lifecycle code MUST use layout-aware projection/state update paths instead of legacy root-status helpers.

#### Scenario: Running transition uses projection service
- **WHEN** a request-bound attempt starts
- **THEN** the running transition writes `.state/<namespace>/state.json`
- **AND** it does not call a root-only status writer.

#### Scenario: Canceled preflight transition uses projection service
- **WHEN** cancellation is detected before an attempt executes for a request-bound run
- **THEN** the canceled terminal state and result are written through layout-aware projection finalization.

#### Scenario: Auth timeout update is layout-aware
- **WHEN** auth reconciliation marks a request-bound run waiting-auth or failed
- **THEN** the update targets `.state/<namespace>/state.json`
- **AND** root-only status helpers are not used for current truth.
