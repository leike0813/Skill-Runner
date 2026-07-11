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
## Requirements

### Requirement: CodeBuddy authentication MUST expose two virtual providers

The auth strategy MUST expose startable oauth_proxy/auth_code_or_url entries for codebuddy-cn and codebuddy-global, mapped respectively to SDK environments internal and public.

#### Scenario: User selects the global entry point
- **WHEN** an auth session starts with provider codebuddy-global
- **THEN** the isolated worker authenticates with environment public and cannot select a caller-supplied endpoint
### Requirement: CodeBuddy SDK authentication MUST be process isolated

The official SDK MUST run in a helper process with temporary HOME/XDG/config directories and a whitelisted environment, and the service MUST terminate descendants and remove temporary state on cancel, timeout, or failure.

#### Scenario: Authentication is canceled while waiting for the browser
- **WHEN** the auth session is canceled
- **THEN** the worker and its CLI descendants terminate and no temporary token/config directory remains
### Requirement: CodeBuddy browser authentication success MUST automatically resume waiting work

The browser-only CodeBuddy SDK flow MUST complete through canonical auth-session polling and MUST NOT require a chat reply. A successful completion MUST issue at most one resume ticket for the waiting attempt; failed, expired, or canceled authentication MUST issue none.

#### Scenario: Browser authentication succeeds
- **WHEN** the isolated worker stores the selected provider credential and the auth session reaches succeeded
- **THEN** the waiting job is automatically requeued exactly once

