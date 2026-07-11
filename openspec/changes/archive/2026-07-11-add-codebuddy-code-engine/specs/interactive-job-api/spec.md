## ADDED Requirements

### Requirement: CodeBuddy jobs MUST select a virtual provider

Job creation with engine=codebuddy MUST require engine_options.provider_id equal to codebuddy-cn or codebuddy-global, including when model is omitted, and MUST reject invalid selection before cache lookup and process launch.

#### Scenario: CodeBuddy job omits provider
- **WHEN** the create request supplies no CodeBuddy provider
- **THEN** the API returns a structured validation error without reading cache or starting the CLI

### Requirement: CodeBuddy provider identity MUST survive waiting and resume

The selected provider MUST remain attached to the execution request, authentication challenge, session handle, and resumed attempt.

#### Scenario: Global attempt waits for reauthentication
- **WHEN** the matching browser authentication session completes successfully
- **THEN** the resumed attempt uses the global credential and global config directory

#### Scenario: Preflight authentication has no session handle
- **WHEN** a missing or expired credential is repaired before the CodeBuddy CLI produced a session handle
- **THEN** the automatically requeued attempt starts a new CodeBuddy session for the same provider

### Requirement: CodeBuddy browser auth projection MUST distinguish selection from an active challenge

A CodeBuddy `challenge_active` projection MUST expose the locked provider and selected method without advertising the method as an unselected choice. A repeated selection carrying the active session identity MUST be handled idempotently.

#### Scenario: Client refresh races with CodeBuddy challenge creation
- **GIVEN** the single CodeBuddy auth method has already created a browser challenge
- **WHEN** a client retries that method with the same `auth_session_id`
- **THEN** the backend returns accepted without starting another SDK auth session
- **AND** subsequent challenge status exposes an empty `available_methods` list
