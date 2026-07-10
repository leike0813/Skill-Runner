## ADDED Requirements

### Requirement: CodeBuddy routing environment MUST be service managed

CodeBuddy requests MUST reject run-local overrides of CODEBUDDY_AUTH_TOKEN, CODEBUDDY_API_KEY, CODEBUDDY_INTERNET_ENVIRONMENT, CODEBUDDY_BASE_URL, and CODEBUDDY_CONFIG_DIR before cache lookup and process launch. The adapter MUST remove inherited values and inject managed values.

#### Scenario: Request attempts to change the environment
- **WHEN** runtime_options.env contains CODEBUDDY_INTERNET_ENVIRONMENT
- **THEN** validation fails without consulting cache or starting a subprocess

### Requirement: CodeBuddy cache policy MUST remain caller controlled

The integration MUST NOT force no_cache and MUST NOT add account identity or credential generation to the cache key; existing provider and model engine options remain cache identity inputs.

#### Scenario: Provider account is replaced
- **WHEN** a caller submits the same cacheable request without no_cache=true
- **THEN** normal cache policy applies and documentation warns that a previous cached result may be reused
