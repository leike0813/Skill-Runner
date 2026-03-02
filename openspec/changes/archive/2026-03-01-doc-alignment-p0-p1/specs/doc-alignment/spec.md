## Purpose

Documentation alignment spec — ensures documentation files accurately reference actual code paths, structures, and components.

## Requirements

### Requirement: SSOT path references SHALL match existing files

All file paths cited in `AGENTS.md` SSOT table and documentation files SHALL resolve to existing files in the repository.

#### Scenario: AGENTS.md path validation
- **WHEN** a developer or AI agent reads the SSOT navigation table in `AGENTS.md`
- **THEN** every `server/**/*.py` path listed SHALL correspond to an existing file

#### Scenario: Statechart doc path validation
- **WHEN** `docs/session_runtime_statechart_ssot.md` references an implementation file
- **THEN** the referenced path SHALL exist and contain the statechart implementation

### Requirement: Project structure documentation SHALL reflect current directory tree

The `docs/project_structure.md` file SHALL accurately describe the current directory hierarchy of the `server/` package.

#### Scenario: Engine directory structure
- **WHEN** a reader reviews the server directory tree in `project_structure.md`
- **THEN** the document SHALL list `server/engines/{codex,gemini,iflow,opencode}/` as engine sub-packages

#### Scenario: Runtime layer presence
- **WHEN** a reader reviews the server directory tree
- **THEN** the document SHALL list `server/runtime/` with sub-packages `{adapter,auth,execution,observability,protocol,session}`

### Requirement: Core components documentation SHALL cover all active modules

`docs/core_components.md` SHALL list components by their current file paths and cover all 4 architectural layers (Runtime, Services, Engines, Routers).

#### Scenario: No stale component paths
- **WHEN** a reader looks up a component path in `core_components.md`
- **THEN** the referenced path SHALL exist in the current codebase

### Requirement: README SHALL list all supported engines

`README.md` engine references SHALL include every engine available in `server/engines/`.

#### Scenario: OpenCode engine presence
- **WHEN** a reader reviews supported engines in README
- **THEN** OpenCode SHALL be listed alongside Codex, Gemini CLI, and iFlow CLI

### Requirement: Archived documents SHALL carry visible deprecation notice

Documents that reflect historical planning (not current state) SHALL display a deprecation notice at the top.

#### Scenario: dev_guide.md archive notice
- **WHEN** a reader opens `docs/dev_guide.md`
- **THEN** the first visible content SHALL be a deprecation/archive warning directing to current references
