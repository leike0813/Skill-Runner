## MODIFIED Requirements

### Requirement: Claude auth transports are supported

The engine auth layer SHALL support Claude through the existing `oauth_proxy` and `cli_delegate` transports.

#### Scenario: Start Claude auth session

- **WHEN** a caller starts an auth session for `engine=claude`
- **THEN** the system MUST accept `transport=oauth_proxy`
- **AND** it MUST accept `transport=cli_delegate`
- **AND** it MUST not introduce a new transport type

### Requirement: Claude oauth_proxy supports localhost callback and manual fallback

Claude OAuth proxy SHALL support both automatic localhost callback and manual code-or-URL fallback.

#### Scenario: Claude callback mode

- **WHEN** a Claude oauth_proxy session starts in callback mode
- **THEN** it MUST use a fixed localhost callback endpoint at `127.0.0.1:51123/callback`
- **AND** successful completion MUST persist credentials into `${CLAUDE_CONFIG_DIR}/.credentials.json`

#### Scenario: Claude manual fallback mode

- **WHEN** a Claude oauth_proxy session cannot rely on automatic callback
- **THEN** it MUST allow manual code-or-URL submission
- **AND** successful completion MUST persist credentials into `${CLAUDE_CONFIG_DIR}/.credentials.json`
