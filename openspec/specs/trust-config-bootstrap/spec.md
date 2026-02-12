# trust-config-bootstrap Specification

## Purpose
TBD - created by archiving change run-folder-trust-management. Update Purpose after archive.
## Requirements
### Requirement: Bootstrap trust config files at container startup
At container startup, the system MUST ensure trust configuration artifacts required by Codex and Gemini exist and are valid.

#### Scenario: Create missing Gemini trusted folders file
- **WHEN** `~/.gemini/trustedFolders.json` does not exist
- **THEN** the system creates the file with a top-level JSON object (`{}`)

#### Scenario: Repair invalid Gemini trusted folders file
- **WHEN** `~/.gemini/trustedFolders.json` exists but is not a valid JSON object
- **THEN** the system repairs it to a valid JSON object and preserves a backup of the previous content

### Requirement: Bootstrap trusted parent run directory
At startup, the system MUST pre-register the run parent directory as trusted for Codex and Gemini.

#### Scenario: Bootstrap Codex parent trust
- **WHEN** startup initializes runtime environment
- **THEN** Codex config contains `projects."<runs_parent>".trust_level = "trusted"`

#### Scenario: Bootstrap Gemini parent trust
- **WHEN** startup initializes runtime environment
- **THEN** Gemini trusted folders map contains `"<runs_parent>": "TRUST_FOLDER"`

### Requirement: Bootstrap is idempotent
Repeated startup runs MUST preserve valid configuration and avoid duplicate or conflicting trust entries.

#### Scenario: Startup rerun with existing trust entries
- **WHEN** startup logic executes multiple times
- **THEN** trust entries for run parent remain correct without duplicated/invalid structure

