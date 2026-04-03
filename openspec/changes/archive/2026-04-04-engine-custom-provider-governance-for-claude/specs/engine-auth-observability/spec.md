## MODIFIED Requirements

### Requirement: Claude official auth and custom-provider configuration are separate flows

The engine auth layer SHALL keep Claude official authentication separate from third-party provider configuration.

#### Scenario: official Claude model uses official auth

- **WHEN** a Claude run requests an official model from the official snapshot catalog
- **THEN** the system MUST only use the existing official Claude auth transports
- **AND** it MUST NOT route the run into custom-provider configuration flow

#### Scenario: custom Claude model uses provider-config flow

- **WHEN** a Claude run requests a strict `provider/model` custom model
- **THEN** the system MUST use a dedicated auth path with `transport=provider_config`
- **AND** it MUST use `auth_method=custom_provider`
- **AND** it MUST NOT reuse official OAuth or CLI login transport semantics
