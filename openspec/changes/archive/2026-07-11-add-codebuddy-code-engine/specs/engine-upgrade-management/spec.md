## ADDED Requirements

### Requirement: CodeBuddy CLI MUST be managed installable

The engine manager MUST install and upgrade CodeBuddy from npm package @tencent-ai/codebuddy-code using the managed lifecycle and status semantics of npm-backed engines.

#### Scenario: Managed installation completes
- **WHEN** a CodeBuddy install request succeeds
- **THEN** the status cache refreshes and reports the detected version

### Requirement: CodeBuddy binary detection MUST support aliases

Binary discovery MUST recognize codebuddy, cbc, and supported Windows command variants without executing a host credential probe.

#### Scenario: Only the cbc alias is installed
- **WHEN** the binary manager searches for CodeBuddy
- **THEN** it resolves the alias as the CodeBuddy CLI executable
