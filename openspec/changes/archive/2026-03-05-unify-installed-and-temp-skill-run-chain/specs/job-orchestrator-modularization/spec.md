## ADDED Requirements

### Requirement: Request persistence MUST be DB-only

Orchestration MUST persist request lifecycle in database storage and MUST NOT rely on request filesystem directories as canonical request state.

#### Scenario: request data persisted without request dir
- **WHEN** a request is created
- **THEN** request metadata MUST be stored in unified request DB model
- **AND** no request directory is required for canonical persistence

### Requirement: Upload staging MUST be request-scoped temporary storage

Orchestration MUST stage uploads in request-local temporary storage during upload handling, then decide cache hit/miss before writing to run directory.

#### Scenario: cache hit discards temporary staging
- **WHEN** upload is processed and cache hits
- **THEN** system MUST bind cached run
- **AND** system MUST discard temporary staging without creating run uploads directory

#### Scenario: cache miss promotes staging to run directory
- **WHEN** upload is processed and cache misses
- **THEN** system MUST create run directory
- **AND** system MUST promote staged uploads into run directory

### Requirement: Runtime chain MUST not branch by temp request identity

Orchestration MUST execute interaction/auth/resume lifecycle from unified request identity and MUST NOT require temp-request-specific branching.

#### Scenario: resume scheduling without temp_request_id branch
- **WHEN** system schedules resumed attempt
- **THEN** orchestration MUST use unified request record only
- **AND** MUST NOT depend on temp request store lookup
