## ADDED Requirements

### Requirement: Data reset targets SHALL align with unified persistence
System data reset target resolution SHALL follow the unified persistence layout and MUST include only canonical runtime databases.

#### Scenario: Build reset targets
- **WHEN** reset targets are computed
- **THEN** canonical DB targets SHALL include `runs.db` and `engine_upgrades.db`
- **AND** `skill_installs.db` / `temp_skill_runs.db` SHALL NOT be required DB targets

### Requirement: Data reset SHALL cover tmp uploads and ui shell session directories
Reset target computation SHALL include runtime auxiliary directories under data root used by current implementation.

#### Scenario: Optional path coverage
- **WHEN** reset targets are computed
- **THEN** optional targets SHALL include `data/tmp_uploads` and `data/ui_shell_sessions`
