## ADDED Requirements

### Requirement: Kilo CLI MUST be managed installable

The engine management layer SHALL support managed installation of `@kilocode/cli`.

#### Scenario: Install Kilo Code

- **WHEN** the user requests install or upgrade for `kilo`
- **THEN** the system MUST run npm install for the package declared in Kilo adapter profile
- **AND** it MUST verify one of the profile-declared Kilo binary candidates is available

### Requirement: Kilo CLI binary detection MUST support aliases

Kilo binary detection SHALL support both `kilo` and `kilocode` aliases across supported platforms.

#### Scenario: Detect Kilo CLI

- **WHEN** the system resolves the Kilo command
- **THEN** it MUST check profile-declared candidates including `kilo` and `kilocode`
## Requirements

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

