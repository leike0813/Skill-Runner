## MODIFIED Requirements

### Requirement: Engine Run Folder Trust Lifecycle

Run-folder trust strategies MUST support run-scoped registration and cleanup for every engine that participates in managed trust lifecycle.

#### Scenario: Claude run trust is registered and removed per run

- **WHEN** a Claude run/session directory is prepared for execution
- **THEN** the system registers the normalized absolute run/session path in Claude trust storage before CLI launch
- **AND** on completion the system removes that path as a best-effort cleanup action
- **AND** cleanup failure does not change terminal run/session status

#### Scenario: Claude stale run entries are cleaned without touching user projects

- **WHEN** stale trust cleanup runs for Claude
- **THEN** only run child paths derived from the managed runs root are eligible for deletion
- **AND** unrelated user-managed project entries remain untouched
