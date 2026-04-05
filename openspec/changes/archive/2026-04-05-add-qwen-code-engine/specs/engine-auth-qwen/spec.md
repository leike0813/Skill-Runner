## ADDED Requirements

### Requirement: Qwen authentication providers MUST be explicit

The Qwen engine SHALL expose three explicit official authentication providers.

#### Scenario: List Qwen providers

- **WHEN** the UI or management API queries Qwen auth providers
- **THEN** the system MUST expose:
  - `qwen-oauth`
  - `coding-plan-china`
  - `coding-plan-global`

### Requirement: Qwen OAuth MUST use device-authorization semantics in oauth_proxy

The `qwen-oauth` provider SHALL use device-authorization style flow under `oauth_proxy`.

#### Scenario: Start Qwen OAuth session

- **WHEN** user selects `provider_id=qwen-oauth` with `transport=oauth_proxy`
- **THEN** the system MUST request a device code from the Qwen OAuth endpoint
- **AND** it MUST return `auth_url` and `user_code`
- **AND** it MUST wait for user confirmation before token polling

#### Scenario: Complete Qwen OAuth session

- **WHEN** user submits confirmation input after finishing browser authorization
- **THEN** the system MUST poll the token endpoint until authorized or timed out
- **AND** successful completion MUST write `.qwen/oauth_creds.json`

### Requirement: Coding Plan providers MUST configure API-key-backed settings

The `coding-plan-china` and `coding-plan-global` providers SHALL collect an API key and write Qwen settings accordingly.

#### Scenario: Configure Coding Plan China

- **WHEN** user selects `coding-plan-china`
- **THEN** the system MUST request an API key
- **AND** it MUST write `.qwen/settings.json` with the China endpoint configuration

#### Scenario: Configure Coding Plan Global

- **WHEN** user selects `coding-plan-global`
- **THEN** the system MUST request an API key
- **AND** it MUST write `.qwen/settings.json` with the Global endpoint configuration

### Requirement: Qwen credentials import MUST be limited to qwen-oauth in this phase

The authentication system SHALL only expose import-based credentials bootstrap for `qwen-oauth` in this phase.

#### Scenario: Import Qwen OAuth credentials

- **WHEN** user imports credentials for `provider_id=qwen-oauth`
- **THEN** the system MUST require `oauth_creds.json`
- **AND** it MUST validate that the file contains `access_token` or `refresh_token`
- **AND** it MUST write `.qwen/oauth_creds.json`

#### Scenario: Coding Plan providers do not expose import flow

- **WHEN** user selects `coding-plan-china` or `coding-plan-global`
- **THEN** the management/UI import entry MUST NOT be exposed

### Requirement: Qwen auth strategy configuration

The authentication strategy SHALL define provider-specific transports and methods.

#### Scenario: Qwen OAuth provider

- **auth_mode**: `oauth`
- **transports**:
  - `oauth_proxy`: methods `["auth_code_or_url"]`
  - `cli_delegate`: methods `["auth_code_or_url"]`

#### Scenario: Coding Plan providers

- **auth_mode**: `api_key`
- **transports**:
  - `oauth_proxy`: methods `["api_key"]`
  - `cli_delegate`: methods `["api_key"]`
