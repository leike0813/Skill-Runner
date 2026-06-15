## ADDED Requirements

### Requirement: RunStore MUST persist workspace metadata for logical runs
RunStore SHALL persist workspace identity, namespace, source request, actual runner-owned paths, and lineage tokens for each logical run.

#### Scenario: Persist metadata for new workspace run
- **WHEN** a normal request creates a run
- **THEN** RunStore stores its `workspace_id`, `workspace_dir`, `workspace_namespace`, `result_path`, `input_manifest_path`, and `workspace_output_token`

#### Scenario: Persist metadata for reused workspace run
- **WHEN** a request reuses a previous request workspace
- **THEN** RunStore stores the same `workspace_id` and `workspace_dir` as the source request
- **AND** stores a new `workspace_namespace`
- **AND** stores `workspace_source_request_id` and `workspace_input_token`

#### Scenario: Cached run exposes workspace metadata
- **WHEN** a request binds to a cached run
- **THEN** RunStore exposes the cached run's workspace metadata and output token to the request record

