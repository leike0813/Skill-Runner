## MODIFIED Requirements

### Requirement: Trust Config Bootstrap

Trust bootstrap MUST be engine-specific at the persistence layer while remaining centrally dispatched.

#### Scenario: Claude repairs malformed trust config

- **WHEN** Claude trust storage file is missing or malformed
- **THEN** the strategy repairs it into a valid top-level object
- **AND** initializes a valid `projects` object when needed
- **AND** preserves a best-effort backup of the malformed file before repair

#### Scenario: Claude parent trust bootstrap is skipped

- **WHEN** the trust manager performs parent bootstrap across registered strategies
- **THEN** Claude's strategy performs no write for the runs parent path
- **AND** only run/session scoped Claude trust entries are managed dynamically
