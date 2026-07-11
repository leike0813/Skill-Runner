## ADDED Requirements

### Requirement: Engine status cache service supports codebuddy

The engine status cache MUST maintain a stable codebuddy row for installed/version/update/error state without synchronously probing authentication on management reads.

#### Scenario: Summary is read during a failed probe
- **WHEN** the most recent CodeBuddy probe failed
- **THEN** the cached engine row remains present with bounded error metadata

### Requirement: CodeBuddy status refresh MUST be independent from static models

CodeBuddy installation status refresh MUST NOT execute model discovery or create provider model-cache state. Model listing MUST remain available from the engine-local pinned manifest independently of installation and credential status.

#### Scenario: CodeBuddy is not installed
- **WHEN** management reads the CodeBuddy model list
- **THEN** the generic registry returns the pinned provider-qualified snapshot without starting a CodeBuddy subprocess
