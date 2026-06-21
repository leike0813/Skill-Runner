## MODIFIED Requirements

### Requirement: File inputs MUST resolve from uploads-relative paths
Skill file inputs MUST continue to resolve from `run_dir/uploads/<input value>`.
Workspace file bindings MUST preserve this contract by materializing the source file to `uploads/<target_path>` while keeping `input[input_key]` equal to `target_path`.

#### Scenario: bound file input resolves at execution time
- **WHEN** a workspace file binding materializes `source_path` to `uploads/<target_path>`
- **AND** `input[input_key]` equals `target_path`
- **THEN** execution-time input context resolves the file input from `run_dir/uploads/<target_path>`

### Requirement: Workspace file binding paths MUST be safe relative paths
`source_path` MUST be a safe workspace-relative file path.
`target_path` MUST be a safe uploads-relative file path.
Both MUST reject absolute paths, empty paths, `.`, `..`, traversal, and directory targets.

#### Scenario: unsafe binding path is rejected
- **WHEN** a binding path is absolute or contains traversal
- **THEN** the backend rejects the request before creating a run

#### Scenario: binding target overwrites uploaded file
- **WHEN** an upload zip contains `target_path`
- **AND** a workspace file binding targets the same path
- **THEN** the binding materialized file is used for the final uploads content and input manifest
