## ADDED Requirements

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
