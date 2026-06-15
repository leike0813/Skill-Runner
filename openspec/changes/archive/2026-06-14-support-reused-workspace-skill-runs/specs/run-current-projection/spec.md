## ADDED Requirements

### Requirement: Run projections MUST expose workspace diagnostics
Run status and management projections SHALL expose physical workspace and actual runner-owned path diagnostics.

#### Scenario: Status includes workspace diagnostics
- **WHEN** a client reads a request status or management run detail
- **THEN** the response includes `workspaceDir`, `resultJsonPath`, and `inputManifestPath` when known

#### Scenario: Diagnostics follow cached run binding
- **WHEN** a request is served from cache
- **THEN** its status diagnostics reference the cached run's actual workspace/result/input-manifest paths
