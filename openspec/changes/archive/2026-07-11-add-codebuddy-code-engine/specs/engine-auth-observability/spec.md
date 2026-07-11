## ADDED Requirements

### Requirement: CodeBuddy auth observability MUST be provider-scoped and redacted

Authentication status, errors, and runtime reauthorization signals MUST identify the selected virtual provider while redacting token-like values, callback secrets, and worker stderr secrets.

#### Scenario: Domestic runtime returns unauthorized
- **WHEN** a codebuddy-cn attempt produces a high-confidence 401 or login-required result in redacted stdout or stderr
- **THEN** waiting-auth guidance targets codebuddy-cn and no credential value appears in logs, events, or bundles

### Requirement: Explicit provider options MUST outrank parser inference

Auth orchestration MUST resolve provider identity from explicit engine_options.provider_id before model selectors or parser fallbacks.

#### Scenario: Model selector omits a provider prefix
- **WHEN** the request explicitly selects codebuddy-global and an auth signal lacks provider metadata
- **THEN** reauthorization is routed to codebuddy-global

### Requirement: CodeBuddy waiting-auth status polling MUST preserve request audit layout

Status reconciliation for a waiting CodeBuddy job MUST open its run-scope log mirror with the request-owned namespaced audit directory from persisted layout metadata.

#### Scenario: Client polls a missing-credential job
- **WHEN** a CodeBuddy job has entered waiting_auth before its task CLI started
- **THEN** status polling succeeds and writes run-scope logs under the persisted audit directory without guessing a workspace-relative fallback
