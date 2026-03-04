## MODIFIED Requirements

### Requirement: Dedicated orchestration services MUST preserve run behavior

The system MUST provide dedicated orchestration services for bundle, filesystem snapshot, audit, interaction lifecycle, restart recovery, and run-folder bootstrap while preserving the existing run behavior and output semantics.

#### Scenario: Create-run materializes the run-local skill snapshot once
- **WHEN** orchestration creates a run from an installed or temporary skill source
- **THEN** the orchestration layer MUST materialize the run-local skill snapshot exactly once
- **AND** later attempts MUST consume that snapshot in place

#### Scenario: Resumed attempt consumes existing snapshot only
- **GIVEN** create-run has already materialized the canonical run-local skill snapshot
- **WHEN** a later resumed attempt is prepared by orchestration services
- **THEN** orchestration MUST continue with the existing snapshot manifest
- **AND** MUST NOT delegate skill installation work to attempt-stage adapter helpers

#### Scenario: Orchestration does not reopen source selection during resume
- **GIVEN** a run-local skill snapshot already exists for the run
- **WHEN** orchestration resolves the skill manifest for a later attempt
- **THEN** orchestration MUST treat the run-local snapshot as the canonical source for that run
- **AND** MUST NOT reopen normal source selection through registry or `skill_override`
