## ADDED Requirements

### Requirement: Qwen bootstrap configuration MUST be written to managed agent home

The bootstrap system SHALL write Qwen configuration to the managed agent home directory.

#### Scenario: Write Qwen bootstrap configuration

- **WHEN** the system bootstraps Qwen engine
- **THEN** it MUST create `agent_config/qwen/.qwen/` directory
- **AND** it MUST write `bootstrap.json` to `agent_config/qwen/.qwen/settings.json`

### Requirement: Qwen run-folder configuration MUST use the shared layering contract

Run-folder configuration SHALL be written to `run_dir/.qwen/settings.json` using the shared config-layering order.

#### Scenario: Compose Qwen run-folder settings

- **WHEN** a run is executed with Qwen engine
- **THEN** the system MUST create `run_dir/.qwen/` directory
- **AND** it MUST merge `engine_default -> skill defaults -> runtime overrides -> enforced`
- **AND** it MUST write the result to `run_dir/.qwen/settings.json`

### Requirement: Qwen skill injection MUST copy to run-local snapshot

Skills SHALL be copied to `run_dir/.qwen/skills/<skill_id>/`.

#### Scenario: Inject skill into Qwen run folder

- **WHEN** a run is materialized with a skill
- **THEN** the skill MUST be copied to `run_dir/.qwen/skills/<skill_id>/`
- **AND** the skill MUST include `SKILL.md` and declared assets

### Requirement: Workspace manager supports qwen workspace layout

The workspace manager SHALL support Qwen-specific workspace subdirectories.

#### Scenario: Create Qwen workspace subdirectories

- **WHEN** a run folder is created for Qwen engine
- **THEN** it MUST create `.qwen/`
- **AND** it MUST create `.qwen/skills/`

### Requirement: installer bootstrap defaults include qwen

Default managed bootstrap/ensure SHALL include `qwen` as a supported engine target.

#### Scenario: default ensure set contains qwen

- **WHEN** the system resolves its default managed bootstrap engines
- **THEN** `qwen` MUST be included in that default set
