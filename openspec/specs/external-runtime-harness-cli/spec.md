## ADDED Requirements

### Requirement: Agent harness skill injection includes kilo

The harness skill injection system SHALL support Kilo as a target engine.

#### Scenario: Inject skills into Kilo run folder

- **WHEN** the harness runs with `engine=kilo`
- **THEN** it MUST copy skills to `run_dir/.kilo/skills/`
- **AND** it MUST report the injection target as supported
## Requirements

### Requirement: Agent harness skill injection includes codebuddy

The external runtime harness MUST derive CodeBuddy skill materialization from its adapter profile and place skills under .codebuddy/skills.

#### Scenario: Harness prepares a CodeBuddy run
- **WHEN** a compatible skill is injected
- **THEN** the skill files appear under .codebuddy/skills/<skill-id> and the root contains CODEBUDDY.md

