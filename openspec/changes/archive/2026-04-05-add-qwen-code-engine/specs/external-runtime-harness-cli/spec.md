## ADDED Requirements

### Requirement: Agent harness skill injection includes qwen

The agent harness skill injection system SHALL support `qwen` as a target engine.

#### Scenario: Inject skills into qwen run folder

- **WHEN** agent harness runs with `engine=qwen`
- **THEN** it MUST copy skills to `run_dir/.qwen/skills/`
- **AND** it MUST return `supported=True` in the injection result
- **AND** it MUST patch SKILL.md files for the execution mode

### Requirement: Agent harness skill injection includes claude

The agent harness skill injection system SHALL support `claude` as a target engine.

#### Scenario: Inject skills into claude run folder

- **WHEN** agent harness runs with `engine=claude`
- **THEN** it MUST copy skills to `run_dir/.claude/skills/`
- **AND** it MUST return `supported=True` in the injection result
- **AND** it MUST patch SKILL.md files for the execution mode
