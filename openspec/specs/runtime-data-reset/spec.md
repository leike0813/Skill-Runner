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

### Requirement: Data reset targets SHALL align with unified persistence
System data reset target resolution SHALL follow the unified persistence layout and MUST include only canonical runtime databases.

#### Scenario: Build reset targets
- **WHEN** reset targets are computed
- **THEN** canonical DB targets SHALL include `runs.db` only
- **AND** engine upgrades / skill installs metadata SHALL be persisted in `runs.db` tables
- **AND** `engine_upgrades.db` / `skill_installs.db` / `temp_skill_runs.db` SHALL NOT be required DB targets

### Requirement: Data reset SHALL cover tmp uploads and ui shell session directories
Reset target computation SHALL include runtime auxiliary directories under data root used by current implementation.

#### Scenario: Optional path coverage
- **WHEN** reset targets are computed
- **THEN** optional targets SHALL include `data/tmp_uploads` and `data/ui_shell_sessions`
