# run-current-projection Delta

## MODIFIED Requirements

### Requirement: Read projections MUST resolve workspace layout first
Status, list, detail, logs, events, chat, and management projections MUST prefer persisted workspace layout over legacy run directories.

#### Scenario: Run list and detail read physical workspace
- **GIVEN** a request record has `workspace_dir`
- **WHEN** list or detail projections read current state
- **THEN** they read `.state/<namespace>/state.json` under that workspace
- **AND** they do not require `data/runs/<run_id>` to exist.

#### Scenario: Logs read namespaced audit under workspace
- **GIVEN** a request record has `workspace_dir` and `workspace_namespace`
- **WHEN** log tail or log range is requested
- **THEN** stdout/stderr are read from `.audit/<namespace>/`
- **AND** legacy `.audit/stdout.*.log` is only a fallback.
