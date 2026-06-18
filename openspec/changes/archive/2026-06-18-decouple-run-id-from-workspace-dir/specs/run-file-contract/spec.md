# run-file-contract Delta

## MODIFIED Requirements

### Requirement: New request-bound runs MUST use workspace_dir as file root
New request-bound runs MUST use the persisted physical `workspace_dir` as the root for runner-owned files.

#### Scenario: New run allocates workspace root
- **WHEN** a non-reuse request creates a run
- **THEN** the backend creates `data/workspaces/<workspace_id>`
- **AND** `workspace_id` defaults to the new `run_id`
- **AND** the backend does not create `data/runs/<run_id>`.

#### Scenario: Reuse run inherits workspace root
- **GIVEN** a source request completed successfully with persisted workspace metadata
- **WHEN** a later request uses `runtime_options.workspace.mode = "reuse"`
- **THEN** the new logical run receives a new `run_id`
- **AND** it reuses the source request's `workspace_id` and `workspace_dir`
- **AND** no symlink is created under `data/runs/<new_run_id>`.

### Requirement: Runner-owned files MUST remain namespace-owned
Runner-owned files in a shared workspace MUST use the request's persisted namespace.

#### Scenario: Contracts are namespaced
- **WHEN** output schema contracts are materialized for a request-bound run
- **THEN** `target_output_schema.json` is written under `.audit/<namespace>/contracts/`
- **AND** engine-specific compatible schema artifacts are written in the same contracts directory.

#### Scenario: Bundles are namespaced
- **WHEN** a request-bound bundle is generated
- **THEN** bundle files and manifests are written under `bundle/<namespace>/`
- **AND** root `bundle/run_bundle*.zip` is not current truth for that run.

### Requirement: Legacy run dirs MUST remain readable as fallback
Historical no-layout records MUST remain readable through `data/runs/<run_id>` fallback.

#### Scenario: Legacy record has no workspace metadata
- **GIVEN** a run record has no persisted `workspace_dir`
- **WHEN** a read path resolves its files
- **THEN** the backend may fall back to `data/runs/<run_id>`.
