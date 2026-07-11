## ADDED Requirements

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
