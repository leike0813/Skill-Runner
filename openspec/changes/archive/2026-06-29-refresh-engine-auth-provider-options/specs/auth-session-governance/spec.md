## ADDED Requirements

### Requirement: Removed provider auth sessions MUST fail before session creation
Removed provider IDs SHALL be rejected before creating an auth session.

#### Scenario: OpenCode Google auth is requested
- **WHEN** a client requests an auth session for `engine=opencode` and `provider_id=google`
- **THEN** the request MUST fail as an unsupported provider or unsupported auth combination
- **AND** no auth session MUST be created

#### Scenario: Kilo Google auth is requested
- **WHEN** a client requests an auth session for `engine=kilo` and `provider_id=google`
- **THEN** the request MUST fail as an unsupported provider or unsupported auth combination
- **AND** no auth session MUST be created

#### Scenario: Qwen OAuth auth is requested
- **WHEN** a client requests an auth session for `engine=qwen` and `provider_id=qwen-oauth`
- **THEN** the request MUST fail as an unsupported provider or unsupported auth combination
- **AND** no auth session MUST be created

### Requirement: Qwen API-key sessions MUST write current settings shape
Qwen API-key provider sessions SHALL persist credentials and model provider definitions in the current Qwen settings format.

#### Scenario: Qwen third-party API key succeeds
- **WHEN** a user submits an API key for a Qwen preset provider such as `openrouter`
- **THEN** the session MUST succeed
- **AND** managed `~/.qwen/settings.json` MUST contain `modelProviders.openai`, the provider env key, `security.auth.selectedType=openai`, and a default `model.name`
