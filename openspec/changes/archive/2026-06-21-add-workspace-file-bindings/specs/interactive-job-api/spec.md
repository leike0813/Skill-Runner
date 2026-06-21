## MODIFIED Requirements

### Requirement: Jobs API MUST accept runtime workspace file bindings for reused workspaces
`POST /v1/jobs` MUST accept `runtime_options.workspace.file_bindings` when `runtime_options.workspace.mode` is `reuse`.
Each binding MUST include non-empty string fields `input_key`, `source_request_id`, `source_path`, and `target_path`.

#### Scenario: create request declares a workspace file binding
- **WHEN** a client creates a job with `runtime_options.workspace.mode` set to `reuse`
- **AND** `runtime_options.workspace.file_bindings` contains a binding object
- **THEN** the API accepts the request shape when the binding fields are non-empty strings

#### Scenario: duplicate file binding keys are rejected
- **WHEN** a create or upload request contains duplicate `input_key` values or duplicate `target_path` values in `file_bindings`
- **THEN** the API rejects the request with a 4xx response

#### Scenario: binding input value must match target path
- **WHEN** a binding declares `input_key` and `target_path`
- **THEN** `input[input_key]` MUST exist and equal `target_path`
- **AND** the backend MUST NOT implicitly rewrite `input`
