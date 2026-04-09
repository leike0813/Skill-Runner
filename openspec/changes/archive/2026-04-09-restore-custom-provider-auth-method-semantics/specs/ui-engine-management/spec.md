## ADDED Requirements

### Requirement: management UI auth method menu MUST allow custom_provider when supported
The management UI MUST treat `custom_provider` as a legal auth method menu value when the current engine/provider/transport capability declares provider-config support.

#### Scenario: provider-config menu renders custom_provider
- **WHEN** the UI renders auth methods for a provider-config capable engine/provider
- **THEN** the menu MAY include `custom_provider`
- **AND** it MUST not relabel that option as `api_key`
