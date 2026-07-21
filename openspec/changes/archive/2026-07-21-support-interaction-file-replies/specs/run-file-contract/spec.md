## MODIFIED Requirements

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

#### Scenario: Interaction reply files are namespaced
- **WHEN** files are accepted for a request-bound pending interaction in a shared workspace
- **THEN** the final files are owned by `uploads/.interaction-replies/<namespace>/`
- **AND** they cannot collide with files owned by another logical run sharing the workspace

## ADDED Requirements

### Requirement: Interaction reply files MUST use the canonical workspace input root
The system MUST place managed interaction reply files below the persisted `workspace_dir` in the reserved `uploads/.interaction-replies/<namespace>/<interaction-id>/<receipt-token>/` subtree. The continuation MUST receive workspace-relative POSIX paths only.

#### Scenario: Agent reads a managed interaction file
- **WHEN** the resumed agent resolves a continuation file path against its workspace root
- **THEN** the path addresses the accepted file within the current request namespace

### Requirement: Managed interaction files MUST publish atomically and safely
The system MUST stream files to an exclusively created sibling temporary directory, validate containment and limits, write the manifest, and atomically rename the complete directory. Client filenames MUST be basename-normalized across POSIX and Windows separators, while stored names MUST be generated independently and collision-safe.

#### Scenario: Complete directory is published
- **WHEN** all files and the manifest are valid and durable
- **THEN** one atomic rename exposes the final receipt directory

#### Scenario: Incomplete write is cleaned
- **WHEN** any write, validation, or promotion step fails
- **THEN** temporary files are removed best-effort and no incomplete final directory becomes continuation truth

#### Scenario: Reserved subtree is occupied or traversed
- **WHEN** an initial upload or filesystem entry attempts to occupy, traverse, or symlink the reserved interaction-reply subtree
- **THEN** the system rejects the conflicting path without overwriting existing data
