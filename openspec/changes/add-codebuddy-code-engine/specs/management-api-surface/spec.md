## ADDED Requirements

### Requirement: CodeBuddy management models MUST be provider qualified

GET /v1/engines/codebuddy/models MUST return provider-qualified model IDs and provider metadata and MUST allow both providers to expose the same raw model without collision.

#### Scenario: Both providers expose the same model
- **WHEN** domestic and global snapshots contain glm-5.2
- **THEN** the API returns distinct codebuddy-cn/glm-5.2 and codebuddy-global/glm-5.2 records

### Requirement: Management API MUST expose redacted CodeBuddy credential operations

Engine detail MUST expose only provider credential state, and DELETE /v1/management/engines/{engine}/auth/credentials/{provider_id} MUST delete only a supported selected credential and return engine, provider, deletion result, and missing state.

#### Scenario: Domestic credential is cleared
- **WHEN** the deletion endpoint is called for codebuddy-cn
- **THEN** no raw credential is returned, domestic is missing, and the global credential remains unchanged
