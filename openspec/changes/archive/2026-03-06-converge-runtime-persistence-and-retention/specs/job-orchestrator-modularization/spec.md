## ADDED Requirements

### Requirement: Runtime process leases SHALL persist in runs.db
The runtime process supervisor SHALL persist lease state in `runs.db` table `process_leases` rather than filesystem JSON files.

#### Scenario: Register and close a lease
- **WHEN** a managed process lease is registered and then closed
- **THEN** the lease record SHALL be written to `runs.db.process_leases`
- **AND** lease state transitions SHALL be queryable without reading `data/runtime_process_leases/*.json`

### Requirement: Auxiliary runtime artifacts SHALL be retention-managed
The periodic run cleanup workflow SHALL include auxiliary runtime storage cleanup using existing run retention settings.

#### Scenario: Expired temporary upload staging is removed
- **WHEN** run cleanup executes
- **AND** a `data/tmp_uploads/<request_id>` directory exceeds retention
- **THEN** the directory SHALL be deleted

#### Scenario: Closed process leases are pruned
- **WHEN** run cleanup executes
- **AND** a closed process lease exceeds retention
- **THEN** the corresponding `process_leases` row SHALL be deleted

#### Scenario: Active UI shell sessions are protected
- **WHEN** run cleanup executes
- **AND** a `ui_shell_sessions` directory is associated with an active `ui_shell` lease
- **THEN** cleanup SHALL NOT delete that active session directory
