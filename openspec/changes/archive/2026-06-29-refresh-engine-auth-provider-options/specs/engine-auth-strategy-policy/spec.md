## MODIFIED Requirements

### Requirement: Kilo third-party providers MUST reuse OpenCode provider semantics
Kilo third-party provider IDs, auth modes, menu labels, and conversation methods SHALL follow the OpenCode provider-aware registry unless explicitly overridden for Kilo Gateway.

#### Scenario: Kilo provider registry lists third-party providers
- **WHEN** provider-aware metadata is requested for `kilo`
- **THEN** the registry MUST include `kilo`
- **AND** it MUST include OpenCode-compatible API-key provider IDs such as `deepseek`, `openrouter`, and `anthropic`
- **AND** it MUST NOT include `google`
- **AND** non-Gateway provider metadata MUST match the corresponding OpenCode metadata

## ADDED Requirements

### Requirement: OpenCode-family Google AntiGravity auth MUST NOT be startable
OpenCode and Kilo SHALL NOT expose Google AntiGravity as a provider-aware auth option.

#### Scenario: Strategy capabilities exclude Google AntiGravity
- **WHEN** auth strategy capabilities are listed
- **THEN** `opencode/google` MUST NOT appear under any transport
- **AND** `kilo/google` MUST NOT appear under any transport

### Requirement: OpenCode-family common API-key providers MUST be startable
OpenCode and Kilo SHALL expose common third-party providers as API-key auth sessions.

#### Scenario: API-key provider strategy is available
- **WHEN** auth strategy capabilities are listed
- **THEN** OpenCode and Kilo MUST expose `oauth_proxy/api_key` for `anthropic`, `groq`, `mistral`, `xai`, `cerebras`, `perplexity`, `togetherai`, `deepinfra`, `cohere`, `venice`, and `vercel`

### Requirement: Qwen OAuth MUST NOT be startable
Qwen SHALL NOT expose the discontinued `qwen-oauth` provider through provider-aware auth.

#### Scenario: Qwen strategy excludes qwen-oauth
- **WHEN** auth strategy capabilities are listed
- **THEN** `qwen/qwen-oauth` MUST NOT appear under any transport
- **AND** Qwen providers MUST use `oauth_proxy/api_key`
