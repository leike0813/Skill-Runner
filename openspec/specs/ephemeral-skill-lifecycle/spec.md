# ephemeral-skill-lifecycle Specification

## Purpose
TBD - created by archiving change temporary-skill-upload-run. Update Purpose after archive.
## Requirements
### Requirement: Temporary skill assets must be deleted after terminal run state
The system SHALL remove temporary skill package files and extracted temporary skill content after the associated run reaches a terminal state.

#### Scenario: Cleanup after successful execution
- **WHEN** a temporary-skill run reaches `succeeded`
- **THEN** the system removes temporary-skill staging and package files for that request

### Requirement: Cleanup must also run for failed or canceled runs
The system MUST execute the same temporary-skill cleanup for `failed` and `canceled` terminal states.

#### Scenario: Cleanup after failed execution
- **WHEN** a temporary-skill run reaches `failed` or `canceled`
- **THEN** the system removes temporary-skill staging and package files for that request

### Requirement: Cleanup must not delete run outputs
The system MUST preserve run outputs (`result`, `artifacts`, `logs`) while deleting temporary skill content.

#### Scenario: Preserve outputs during temporary cleanup
- **WHEN** temporary-skill cleanup is executed
- **THEN** run output files remain available according to normal run result and artifact APIs

### Requirement: Orphan temporary files must be recoverable by background cleanup
The system SHALL provide a scheduled background cleanup mechanism to remove orphan temporary-skill files left by interrupted execution flows.

#### Scenario: Remove orphan temporary skill files
- **WHEN** a temporary-skill request has stale temporary files with no active run
- **THEN** the background cleanup mechanism deletes those orphan temporary files

### Requirement: Optional debug retention for temporary skill files
The system MUST support a runtime debug option to keep temporary skill files for diagnostics.

#### Scenario: Keep temporary files in debug mode
- **WHEN** runtime option `debug_keep_temp` is true
- **THEN** immediate temporary-skill cleanup is skipped for that run

### Requirement: Cleanup failure handling is warning-only
If immediate cleanup fails, the system MUST log warning-level diagnostics and defer deletion to scheduled cleanup without request-time retries.

#### Scenario: Immediate cleanup failure
- **WHEN** temporary cleanup operation fails at run terminal state
- **THEN** the run remains terminal, warning is recorded, and scheduled cleanup handles later deletion

