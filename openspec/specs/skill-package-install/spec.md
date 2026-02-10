# skill-package-install Specification

## Purpose
TBD - created by archiving change skill-package-install. Update Purpose after archive.
## Requirements
### Requirement: Accept skill package upload for async install
The system SHALL provide an API endpoint to accept a skill package as a zip upload and initiate an asynchronous installation job.

#### Scenario: Create an async install job
- **WHEN** a client uploads a zip package to the skill-install endpoint
- **THEN** the system returns a unique install request identifier and initial status

### Requirement: Skill package root directory is required
A skill package MUST contain exactly one top-level directory, and its name SHALL be treated as the `skill_id`.

#### Scenario: Missing or ambiguous top-level directory
- **WHEN** the uploaded zip does not contain exactly one top-level directory
- **THEN** the system rejects the package as invalid

### Requirement: Enforce AutoSkill Profile validation
The system MUST validate the uploaded skill package against the Runner AutoSkill Profile before installation.

#### Scenario: Missing required files
- **WHEN** the package is missing any required file (`SKILL.md`, `assets/runner.json`, `assets/input.schema.json`, `assets/output.schema.json`)
- **THEN** the system rejects the package as invalid

### Requirement: Enforce identity consistency
The system MUST enforce that the skill directory name, `assets/runner.json` `id`, and `SKILL.md` frontmatter `name` are identical.

#### Scenario: ID mismatch
- **WHEN** any of the three identifiers do not match
- **THEN** the system rejects the package as invalid

### Requirement: Enforce engine declaration
The system MUST require `assets/runner.json` to declare a non-empty `engines` list.

#### Scenario: Missing engines
- **WHEN** `assets/runner.json` omits `engines` or provides an empty list
- **THEN** the system rejects the package as invalid

### Requirement: Enforce artifacts contract
The system MUST require `assets/runner.json` to declare an artifacts contract suitable for Runner indexing.

#### Scenario: Missing artifacts contract
- **WHEN** `assets/runner.json` omits `artifacts` or declares an empty list
- **THEN** the system rejects the package as invalid

### Requirement: Enforce version presence and monotonic updates
The system MUST require `assets/runner.json` to include a version string, and updates MUST be rejected if the new version is not strictly greater than the installed version.

#### Scenario: Downgrade or equal version
- **WHEN** a package is uploaded for an existing skill and its version is less than or equal to the installed version
- **THEN** the system rejects the update

### Requirement: Preserve existing skill on validation failure
The system MUST NOT modify or archive an existing skill if the uploaded package fails validation.

#### Scenario: Validation failure for existing skill
- **WHEN** an update package fails validation
- **THEN** the existing skill remains unchanged and no archive is created

### Requirement: Refresh skill registry after successful install
After a successful install or update, the system SHALL make the skill available to discovery without requiring a server restart.

#### Scenario: Post-install discovery
- **WHEN** an install job completes successfully
- **THEN** the skill appears in skill discovery results

