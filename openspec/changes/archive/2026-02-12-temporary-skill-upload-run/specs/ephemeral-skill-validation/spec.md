## ADDED Requirements

### Requirement: Temporary skill package structure is mandatory
The system MUST require temporary skill packages to contain exactly one top-level directory and treat that directory name as the temporary `skill_id`.

#### Scenario: Reject invalid top-level layout
- **WHEN** an uploaded temporary skill package has zero or multiple top-level directories
- **THEN** the system rejects the request as invalid

### Requirement: AutoSkill required files must be present for temporary skills
The system MUST require temporary skill packages to include `SKILL.md`, `assets/runner.json`, and all schema files referenced by `runner.json.schemas` (`input`, `parameter`, `output`).

#### Scenario: Reject missing required file
- **WHEN** a temporary skill package is missing any required file
- **THEN** the system rejects the request as invalid

### Requirement: Temporary skill identity fields must match
The system MUST enforce identity consistency across temporary skill directory name, `runner.json.id`, and `SKILL.md` frontmatter `name`.

#### Scenario: Reject identity mismatch
- **WHEN** any temporary skill identity field does not match the others
- **THEN** the system rejects the request as invalid

### Requirement: Temporary skill metadata must satisfy execution constraints
The system MUST require temporary skill metadata to provide a non-empty `engines` list and a non-empty `artifacts` contract before execution.

#### Scenario: Reject invalid metadata contract
- **WHEN** `runner.json` for a temporary skill omits or empties `engines` or `artifacts`
- **THEN** the system rejects the request as invalid

### Requirement: Temporary skill upload must enforce package size limit
The system MUST enforce a configurable package size limit for temporary skill uploads.

#### Scenario: Reject oversized temporary skill package
- **WHEN** the uploaded temporary skill package exceeds configured size limit
- **THEN** the system rejects the request as invalid

### Requirement: Zip extraction must be path-safe
The system MUST reject zip entries that attempt unsafe path traversal or absolute-path extraction.

#### Scenario: Reject zip-slip entry
- **WHEN** a temporary skill package contains `..` or absolute-path zip entries
- **THEN** the system rejects the request as invalid
