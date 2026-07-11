## MODIFIED Requirements

### Requirement: Kilo command defaults MUST be profile declared

Kilo command, workspace, config, and UI shell defaults SHALL be declared in the adapter profile and consumed through shared profile contracts.

#### Scenario: Kilo profile config assets

- **WHEN** runtime and UI shell managers resolve Kilo config assets
- **THEN** runtime config assets MUST point to Kilo config files
- **AND** UI shell config assets MUST point to Kilo config files
- **AND** profile targets MUST preserve `.kilo/kilo.jsonc`

## ADDED Requirements

### Requirement: OpenCode-family command defaults MUST enable thinking

OpenCode-family engines that support a thinking flag SHALL enable it through adapter profile command defaults.

#### Scenario: OpenCode profile defaults

- **WHEN** the runtime builds an OpenCode API command with profile defaults enabled
- **THEN** the defaults MUST include `--format json --thinking`
- **AND** OpenCode-specific defaults MUST NOT be hardcoded in shared command-default modules

#### Scenario: Kilo resume profile defaults

- **WHEN** the runtime builds a Kilo resume command with profile defaults enabled
- **THEN** the defaults MUST include `run --format json --auto --thinking --session`
- **AND** the session id MUST still be appended as the value for `--session`
## Requirements

### Requirement: CodeBuddy headless command defaults MUST be profile declared

The CodeBuddy profile and command builder MUST declare print mode, stream JSON output, bypass permission mode, project-only settings, strict MCP config, optional inline JSON schema, and optional model for start and resume.

#### Scenario: Initial attempt is built
- **WHEN** the adapter builds a start command
- **THEN** it emits every managed headless/configuration flag exactly once and appends the prompt last
### Requirement: Unsupported CodeBuddy process modes MUST not be emitted

Command construction MUST NOT emit continue, worktree, tmux, sandbox, serve, or ACP options.

#### Scenario: A resume command is built
- **WHEN** a persisted session handle is present
- **THEN** only exact -r resume semantics are used
### Requirement: CodeBuddy interactive command defaults MUST be profile declared

The CodeBuddy UI-shell command MUST use the true interactive CLI entry point with project-only settings and MUST NOT contain print mode, stream output, or CLI permission-mode flags.

#### Scenario: Inline terminal command is built
- **WHEN** the UI-shell launch plan is prepared
- **THEN** the command contains `--setting-sources project` and omits `-p`, `--output-format`, and `--permission-mode`

