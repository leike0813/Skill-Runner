## ADDED Requirements

### Requirement: Treat invalid existing skill directory as fresh install candidate
The install workflow MUST determine whether an existing skill directory is a valid installed skill by reading `assets/runner.json` and parsing a valid version.

#### Scenario: Existing directory missing runner metadata
- **GIVEN** `skills/<skill_id>/` exists
- **AND** `assets/runner.json` is missing or invalid
- **WHEN** a package for the same `skill_id` is uploaded
- **THEN** the system MUST NOT enter update flow
- **AND** MUST quarantine the existing directory into `skills/.invalid/`
- **AND** MUST proceed as a fresh install
