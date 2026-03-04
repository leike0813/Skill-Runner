# runtime-data-reset Specification

## Purpose
TBD - created by archiving change complete-runtime-file-contract-cutover-and-scan. Update Purpose after archive.
## Requirements
### Requirement: Data Reset Removes Legacy Runtime Data

Data reset MUST remove both runtime data stores and stale legacy runtime artifacts.

#### Scenario: reset executes in destructive mode
- **WHEN** the shared data reset service runs
- **THEN** it deletes runtime DB files and runtime data directories
- **AND** it removes legacy run artifacts through directory removal of `data/runs`
- **AND** it recreates only the canonical directory skeleton required by the new file contract

### Requirement: Reset Script And Management Reset Stay In Sync

The CLI reset script and management reset endpoint MUST share the same data reset contract.

#### Scenario: reset is invoked from CLI or management API
- **WHEN** either entrypoint requests a reset
- **THEN** both use the shared data reset service
- **AND** both report the same target set and deletion behavior

