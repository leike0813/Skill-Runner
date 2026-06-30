## ADDED Requirements

### Requirement: Kilo auth errors MUST be redacted
Kilo auth flows and config checks SHALL redact tokens, API keys, authorization headers, and provider option secrets from errors, logs, and summaries.

#### Scenario: Kilo Gateway request fails
- **WHEN** Kilo Gateway device auth start or polling fails
- **THEN** the surfaced error MUST include status and safe diagnostic context
- **AND** it MUST NOT include raw token, API-key, cookie, or authorization header values

### Requirement: Kilo runtime auth failures MUST remain observable
Kilo runtime JSONL auth failures SHALL continue to produce auth signals even when Kilo auth sessions are now enabled.

#### Scenario: Kilo paid Gateway model requires login
- **WHEN** Kilo runtime emits a JSONL `type=error` with Gateway auth-required content
- **THEN** the parser MUST mark the turn failed
- **AND** it MUST emit an auth-required signal scoped to Kilo Gateway
