## MODIFIED Requirements

### Requirement: runtime schema MUST accept custom_provider auth enums
The runtime schema MUST accept `custom_provider` as a legal provider-config waiting_auth value.

#### Scenario: pending auth validates custom_provider
- **WHEN** the backend validates a provider-config `PendingAuth` payload
- **THEN** `auth_method` MUST accept `custom_provider`
- **AND** `challenge_kind` MUST accept `custom_provider`
- **AND** `input_kind` MUST accept `custom_provider`

#### Scenario: method selection and auth input accepted validate custom_provider
- **WHEN** the backend validates `pending_auth_method_selection.available_methods` or `auth.input.accepted.submission_kind`
- **THEN** the schema MUST accept `custom_provider`
