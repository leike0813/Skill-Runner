## MODIFIED Requirements

### Requirement: Claude ui shell is restricted to low-risk interaction

The UI engine management layer SHALL treat Claude inline `ui_shell` as a restricted interaction surface intended for authentication and simple question-answering rather than full business execution.

#### Scenario: Claude ui shell session starts with restrictive settings

- **WHEN** a Claude `ui_shell` session is started
- **THEN** the system MUST write session-local Claude settings with a restrictive permission posture
- **AND** it MUST keep sandbox enabled
- **AND** it MUST deny high-risk file editing and shell execution tools by default

#### Scenario: Claude ui shell keeps network available without business-execution write scope

- **WHEN** a Claude `ui_shell` session is prepared
- **THEN** the session MUST preserve network access for authentication and lightweight interaction
- **AND** it MUST NOT inherit the broad write scope used by headless run execution
