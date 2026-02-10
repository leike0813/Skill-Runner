## ADDED Requirements

### Requirement: Archive prior skill version on update
When installing a new version of an existing skill, the system MUST archive the current version to `skills/.archive/<skill_id>/<version>/` before replacing it.

#### Scenario: Archive on update
- **WHEN** a valid update with a higher version is installed
- **THEN** the existing skill directory is moved to `skills/.archive/<skill_id>/<old_version>/`

### Requirement: Archive path uniqueness
The system MUST NOT overwrite an existing archive directory.

#### Scenario: Archive path already exists
- **WHEN** `skills/.archive/<skill_id>/<old_version>/` already exists
- **THEN** the update is rejected and the existing skill remains unchanged

### Requirement: Atomic update behavior
The system MUST ensure that updates are atomic with respect to the active skill directory.

#### Scenario: Update failure after archiving attempt
- **WHEN** an update fails after the archive step
- **THEN** the system reports failure and the active skill directory remains unchanged
