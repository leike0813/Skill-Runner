## ADDED Requirements

### Requirement: Concurrency Policy Must Be YACS-Managed

Runtime concurrency admission MUST read canonical policy values from system configuration (`config.SYSTEM.CONCURRENCY.*`) rather than a standalone JSON file.

#### Scenario: concurrency manager boots with YACS policy

- **WHEN** runtime starts concurrency manager
- **THEN** it reads max queue and concurrency budget from YACS
- **AND** environment overrides MAY refine those values

### Requirement: Runtime Contract Resolution Must Prefer Canonical Contract Paths

Runtime protocol/schema consumers MUST resolve schemas from canonical contract paths first and only use legacy paths as phase migration fallback.

#### Scenario: schema file exists in canonical path

- **WHEN** protocol schema registry loads runtime contract schema
- **THEN** canonical `server/contracts/schemas/*` is used
- **AND** legacy path is not required
