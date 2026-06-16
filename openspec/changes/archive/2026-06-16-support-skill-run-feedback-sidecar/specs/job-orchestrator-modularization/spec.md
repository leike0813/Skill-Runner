## ADDED Requirements

### Requirement: Successful-run feedback sidecar diagnostics MUST be non-terminal

The orchestrator SHALL inspect skill run feedback sidecar state after successful terminal projection and before/around bundle generation without converting sidecar issues into run failures.

#### Scenario: sidecar write/read problem is diagnostic only
- **WHEN** a successful run has no sidecar, an empty sidecar, or a sidecar filesystem read/stat failure
- **THEN** the orchestrator logs the diagnostic condition
- **AND** status update, cache recording, and bundle generation continue according to normal success behavior
