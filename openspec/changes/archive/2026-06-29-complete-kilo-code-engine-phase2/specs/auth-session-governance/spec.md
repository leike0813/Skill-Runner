## ADDED Requirements

### Requirement: Kilo Gateway sessions MUST use oauth_proxy device lifecycle
Kilo Gateway auth sessions SHALL use the existing auth session lifecycle with provider-scoped mutual exclusion, TTL, polling, and terminal state handling.

#### Scenario: Kilo Gateway auth session starts
- **WHEN** an auth session starts for `engine=kilo` and `provider_id=kilo`
- **THEN** the backend MUST request a Kilo device code
- **AND** the session snapshot MUST expose `auth_url`, `user_code`, `expires_at`, `provider_id`, and `transport=oauth_proxy`
- **AND** the session MUST use immediate polling without requiring user input

#### Scenario: Kilo Gateway auth session completes
- **WHEN** Kilo Gateway polling returns an approved token
- **THEN** the session MUST become `succeeded`
- **AND** the token MUST be persisted in a Kilo-readable auth store under managed XDG state

### Requirement: Kilo delegated third-party sessions MUST preserve Kilo identity
Kilo third-party provider auth sessions SHALL reuse OpenCode-compatible behavior while preserving `engine=kilo` in externally visible session state.

#### Scenario: Kilo API-key provider succeeds
- **WHEN** a user submits an API key for a Kilo third-party provider
- **THEN** the session MUST complete through the OpenCode-compatible API-key path
- **AND** the resulting session snapshot MUST still identify the engine as `kilo`
