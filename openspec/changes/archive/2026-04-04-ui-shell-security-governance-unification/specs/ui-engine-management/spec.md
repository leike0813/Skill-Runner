## MODIFIED Requirements

### Requirement: ui shell security source is consistent across engines

The UI engine management layer SHALL apply a consistent governance rule for inline TUI security: profile first, engine config assets second.

#### Scenario: codex remains profile-only

- **WHEN** a Codex `ui_shell` session is started
- **THEN** the system MAY enforce its session restrictions entirely through CLI defaults declared in the adapter profile

#### Scenario: settings-backed engines use engine-owned assets

- **WHEN** a Gemini, iFlow, OpenCode, or Claude `ui_shell` session is started
- **THEN** the system MUST generate the session-local config from engine-owned `ui_shell` assets
- **AND** the security posture observed by the UI shell manager MUST remain equivalent to the previous behavior
