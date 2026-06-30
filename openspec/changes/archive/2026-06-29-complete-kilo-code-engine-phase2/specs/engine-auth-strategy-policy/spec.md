## ADDED Requirements

### Requirement: Kilo auth strategy MUST be provider-aware
The shared auth strategy contract SHALL define Kilo as a provider-aware engine rather than an auth-disabled engine.

#### Scenario: Kilo strategy exposes provider-aware capabilities
- **WHEN** the auth strategy service loads engine auth strategy files
- **THEN** `kilo` MUST validate as a provider-aware engine
- **AND** `provider_id=kilo` MUST expose `oauth_proxy` with `auth_code_or_url`
- **AND** Kilo third-party providers MUST expose the same provider-aware methods as their OpenCode counterparts

### Requirement: Kilo Gateway MUST NOT expose cli_delegate in phase 2
Kilo Gateway auth SHALL use the official `oauth_proxy` device flow and SHALL NOT expose a `cli_delegate` Gateway driver in phase 2.

#### Scenario: Kilo Gateway driver matrix
- **WHEN** driver entries are generated from strategy
- **THEN** `kilo/kilo` MUST register `oauth_proxy/auth_code_or_url`
- **AND** `kilo/kilo` MUST NOT register `cli_delegate`

### Requirement: Kilo third-party providers MUST reuse OpenCode provider semantics
Kilo third-party provider IDs, auth modes, menu labels, and conversation methods SHALL follow the OpenCode provider-aware registry unless explicitly overridden for Kilo Gateway.

#### Scenario: Kilo provider registry lists third-party providers
- **WHEN** provider-aware metadata is requested for `kilo`
- **THEN** the registry MUST include `kilo`
- **AND** it MUST include OpenCode-compatible provider IDs such as `openai`, `google`, `deepseek`, and `opencode-go`
- **AND** non-Gateway provider metadata MUST match the corresponding OpenCode metadata
