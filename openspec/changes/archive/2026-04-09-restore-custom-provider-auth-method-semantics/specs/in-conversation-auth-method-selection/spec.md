## ADDED Requirements

### Requirement: provider-config waiting_auth MUST use custom_provider semantics
The system MUST represent provider-config waiting_auth challenges with `custom_provider` rather than degrading them to `api_key`.

#### Scenario: Claude custom provider enters challenge_active
- **GIVEN** a Claude run requests a third-party provider model
- **WHEN** the backend enters `waiting_auth`
- **THEN** `auth_method` MUST be `custom_provider`
- **AND** `challenge_kind` MUST be `custom_provider`
- **AND** `input_kind` MUST be `custom_provider`
