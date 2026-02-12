# ephemeral-skill-upload-and-run Specification

## Purpose
TBD - created by archiving change temporary-skill-upload-run. Update Purpose after archive.
## Requirements
### Requirement: Two-step temporary run API
The system SHALL provide two-step endpoints under `/v1/temp-skill-runs` for temporary skill execution.

#### Scenario: Create temporary run request
- **WHEN** a client submits a create request to `/v1/temp-skill-runs`
- **THEN** the system returns a unique temporary request identifier

### Requirement: Upload step accepts both temporary skill package and input files
The second step MUST accept temporary skill package upload and run input upload, then start execution.

#### Scenario: Upload and start
- **WHEN** a client uploads temporary skill package and input files to the temporary request upload endpoint
- **THEN** the system validates uploads and starts run execution for that request

### Requirement: Temporary skill execution must be isolated from persistent registry
The system MUST execute temporary-skill runs without writing the temporary skill into the persistent `skills/` registry.

#### Scenario: Execute temporary skill without registry install
- **WHEN** a run is started from a validated temporary skill package
- **THEN** the system executes the run using temporary storage only and does not register the skill in `/v1/skills`

### Requirement: Temporary run status must be queryable
The system SHALL expose request/run status for temporary-skill executions using the same status payload semantics as regular jobs API.

#### Scenario: Query temporary run status
- **WHEN** a client queries status for a temporary-skill request identifier
- **THEN** the system returns status and metadata aligned with normal run lifecycle (`queued`, `running`, `succeeded`, `failed`, `canceled`)

### Requirement: Temporary runs bypass cache
Temporary skill execution MUST bypass cache lookup and cache write-back regardless of runtime options.

#### Scenario: Execute with cache bypass
- **WHEN** a temporary-skill run is submitted
- **THEN** the system executes without reading or writing cache entries

### Requirement: Error code semantics align with jobs API
Temporary run endpoints MUST follow the same error code semantics as jobs API for validation, not-found, queue-full, and internal errors.

#### Scenario: Validation failure response code
- **WHEN** temporary package or input validation fails
- **THEN** the endpoint returns HTTP 400

