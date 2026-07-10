## ADDED Requirements

### Requirement: Engine status cache service supports codebuddy

The engine status cache MUST maintain a stable codebuddy row for installed/version/update/error state without synchronously probing authentication on management reads.

#### Scenario: Summary is read during a failed probe
- **WHEN** the most recent CodeBuddy probe failed
- **THEN** the cached engine row remains present with bounded error metadata

### Requirement: CodeBuddy model status MUST be partitioned by provider

Model snapshots MUST record provider, CLI version, network environment, collection time, status, error, and raw probe path while preserving each provider's last-known-good models on refresh failure.

#### Scenario: Global refresh fails after a prior success
- **WHEN** codebuddy-global help probing fails
- **THEN** its last-known-good catalog remains available and the domestic catalog is unchanged
