## ADDED Requirements

### Requirement: CodeBuddy jobs MUST select a virtual provider

Job creation with engine=codebuddy MUST require engine_options.provider_id equal to codebuddy-cn or codebuddy-global, including when model is omitted, and MUST reject invalid selection before cache lookup and process launch.

#### Scenario: CodeBuddy job omits provider
- **WHEN** the create request supplies no CodeBuddy provider
- **THEN** the API returns a structured validation error without reading cache or starting the CLI

### Requirement: CodeBuddy provider identity MUST survive waiting and resume

The selected provider MUST remain attached to the execution request, authentication challenge, session handle, and resumed attempt.

#### Scenario: Global attempt waits for reauthentication
- **WHEN** the user completes the matching auth session and replies
- **THEN** the resumed attempt uses the global credential and global config directory
