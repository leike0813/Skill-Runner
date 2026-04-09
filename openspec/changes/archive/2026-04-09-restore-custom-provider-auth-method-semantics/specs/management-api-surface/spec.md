## ADDED Requirements

### Requirement: management auth semantics MUST reserve custom_provider for provider-config
The management auth contract MUST recognize `custom_provider` as a legal auth method value when the selected transport is `provider_config`.

#### Scenario: provider-config start request uses custom_provider
- **WHEN** a client starts a provider-config auth session
- **THEN** `auth_method=custom_provider` MUST be accepted
- **AND** it MUST remain distinct from `api_key`
