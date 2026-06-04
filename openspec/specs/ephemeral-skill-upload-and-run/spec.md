# ephemeral-skill-upload-and-run Specification

## Purpose
定义临时 skill 通过统一 Jobs API 进行两步上传-执行的合同、文件接受约束与旧入口下线语义。

## Requirements
### Requirement: Two-step temporary run API
The system SHALL provide temporary skill execution through the unified `/v1/jobs` create/upload flow.

#### Scenario: Create temporary run request
- **WHEN** a client submits `POST /v1/jobs` with `skill_source=temp_upload`
- **THEN** the system returns a unique temporary request identifier
- **AND** the request enters pending upload state

### Requirement: Upload step accepts both temporary skill package and input files
The second step MUST accept temporary skill package upload and run input upload, then start execution.

#### Scenario: Upload and start
- **WHEN** a client uploads `skill_package` and optional input `file` to `POST /v1/jobs/{request_id}/upload`
- **THEN** the system validates uploads and starts run execution for that request

### Requirement: Temporary skill execution must be isolated from persistent registry
The system MUST execute temporary-skill runs without writing the temporary skill into the persistent `skills/` registry.

#### Scenario: Execute temporary skill without registry install
- **WHEN** a run is started from a validated temporary skill package
- **THEN** the system executes the run using temporary storage only and does not register the skill in `/v1/skills`

### Requirement: Temporary run status must be queryable
The system SHALL expose request/run status for temporary-skill executions using the same status payload semantics as regular jobs API.

#### Scenario: Query temporary run status
- **WHEN** a client queries `GET /v1/jobs/{request_id}` for a temporary-skill request identifier
- **THEN** the system returns status and metadata aligned with normal run lifecycle (`queued`, `running`, `succeeded`, `failed`, `canceled`)

### Requirement: Temporary runs follow unified cache policy
Temporary skill execution MUST follow the same execution-mode cache policy as installed skill runs, with the uploaded skill package hash included in the cache key.

#### Scenario: Auto temporary run cache key includes package hash
- **WHEN** a temporary-skill run executes in `auto` mode and cache is enabled
- **THEN** cache lookup/write-back MAY occur
- **AND** the cache key includes the uploaded skill package hash

#### Scenario: Interactive temporary run bypasses cache
- **WHEN** a temporary-skill run executes in `interactive` mode
- **THEN** the system does not read from or write to cache

### Requirement: Error code semantics align with jobs API
Temporary run handling MUST follow Jobs API error code semantics for validation, not-found, queue-full, and internal errors.

#### Scenario: Validation failure response code
- **WHEN** temporary package or input validation fails
- **THEN** the endpoint returns HTTP 400

### Requirement: Legacy temporary skill API MUST remain removed
The system MUST NOT expose create/upload endpoints under `/v1/temp-skill-runs`.

#### Scenario: Legacy create/upload route access
- **WHEN** a client calls `POST /v1/temp-skill-runs` or `POST /v1/temp-skill-runs/{request_id}/upload`
- **THEN** the system returns not-found semantics

### Requirement: Temporary skill injection MUST reuse unified patch pipeline
Temporary skill execution MUST use the same modular `SkillPatcher` pipeline as regular job execution.

#### Scenario: Shared patch entrypoint
- **WHEN** temporary skill package is copied into run workspace
- **THEN** runtime patching uses unified `patch_skill_md` flow
- **AND** does not use a separate completion-only injection branch
