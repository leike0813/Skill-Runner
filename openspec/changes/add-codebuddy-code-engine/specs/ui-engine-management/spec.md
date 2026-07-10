## ADDED Requirements

### Requirement: CodeBuddy management UI MUST expose provider-specific auth controls

The UI MUST display installation/version status and separate domestic and global login, relogin, and clear-credential actions using redacted provider states.

#### Scenario: Only domestic credential exists
- **WHEN** the CodeBuddy management detail is rendered
- **THEN** domestic shows present/relogin/clear and global shows login

### Requirement: CodeBuddy job UI MUST select provider before model

Job creation UI MUST require a CodeBuddy provider selection and filter provider-qualified models accordingly while allowing model to remain empty for CLI default selection.

#### Scenario: User changes from domestic to global
- **WHEN** the provider selector changes
- **THEN** the model selector shows only global models and clears an incompatible domestic selection

### Requirement: CodeBuddy inline TUI MUST remain disabled

Engine shell capability discovery and UI actions MUST not expose an inline CodeBuddy TUI in this release.

#### Scenario: CodeBuddy engine detail loads
- **WHEN** the UI evaluates shell capabilities
- **THEN** no inline terminal launch action is rendered
