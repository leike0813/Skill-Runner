## ADDED Requirements

### Requirement: provider_config/custom_provider snapshots MUST be observable
Auth session observability MUST treat `provider_config/custom_provider` as a first-class waiting_auth semantic.

#### Scenario: provider-config challenge snapshot
- **WHEN** a Claude third-party provider model triggers provider configuration
- **THEN** the auth snapshot MUST expose `transport=provider_config`
- **AND** `auth_method=custom_provider`
- **AND** `challenge_kind=input_kind=custom_provider`
