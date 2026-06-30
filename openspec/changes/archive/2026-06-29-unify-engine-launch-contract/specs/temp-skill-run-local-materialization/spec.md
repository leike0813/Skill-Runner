## MODIFIED Requirements

### Requirement: Temp Skill Is Materialized Into Run-Local Snapshot
Temp skill runs MUST materialize the uploaded skill into a run-local snapshot path derived from the target engine adapter profile.

#### Scenario: Temp run create
- **WHEN** a temp skill run is created
- **THEN** the uploaded skill is unpacked and patched into `<run_dir>/<profile.attempt_workspace.workspace_subdir>/<profile.attempt_workspace.skills_subdir>/<skill_id>/`
- **AND** later attempts and resumed attempts load from that run-local snapshot

### Requirement: Run-local snapshot path MUST be profile-derived
Run-local skill snapshot lookup SHALL use adapter profile workspace metadata rather than hardcoded `.<engine>/skills` construction.

#### Scenario: Snapshot path is resolved
- **WHEN** orchestration materializes or reloads a run-local skill snapshot for an engine
- **THEN** the snapshot path MUST be derived from that engine's adapter profile
- **AND** changing `attempt_workspace.workspace_subdir` or `skills_subdir` in the profile MUST change the snapshot path without editing orchestration code
