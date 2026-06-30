## ADDED Requirements

### Requirement: Agent harness skill injection includes kilo

The harness skill injection system SHALL support Kilo as a target engine.

#### Scenario: Inject skills into Kilo run folder

- **WHEN** the harness runs with `engine=kilo`
- **THEN** it MUST copy skills to `run_dir/.kilo/skills/`
- **AND** it MUST report the injection target as supported
