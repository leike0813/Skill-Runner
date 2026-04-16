# runtime-contract-hygiene Specification

## Purpose
TBD - created by archiving change runtime-contract-hygiene-and-protocol-governance-2026-04-16. Update Purpose after archive.
## Requirements
### Requirement: runtime contracts MUST remain structurally loadable and unique-id clean

The system MUST keep machine-readable runtime contracts structurally valid and free of duplicate rule ids.

#### Scenario: session invariants are loaded by contract tests

- **WHEN** runtime invariant contracts are loaded
- **THEN** `fcmp_mapping.state_changed` MUST remain a valid list of mappings
- **AND** rule identifiers in the same document MUST be unique

### Requirement: parser capability differences MUST have a machine-readable source of truth

The system MUST declare current engine parser capabilities in a machine-readable contract rather than relying on test naming or implementation inspection.

#### Scenario: protocol tests need to know which parser features are promised

- **WHEN** a test or tool needs to determine parser promises for an engine
- **THEN** it MUST be able to read a machine-readable capability matrix
- **AND** that matrix MUST distinguish common protocol guarantees from engine-specific parser capabilities

### Requirement: diagnostic warning taxonomy MUST be stable and non-authoritative

The system MUST expose stable warning taxonomy fields without turning warnings into state-driving signals.

#### Scenario: parser or protocol emits a diagnostic warning

- **WHEN** `diagnostic.warning` is emitted
- **THEN** the payload MUST preserve stable governance metadata such as `severity`, `pattern_kind`, `source_type`, and `authoritative`
- **AND** warnings from parser/protocol fallback paths MUST be non-authoritative

### Requirement: canonical completion-state writes MUST stop using legacy aliases

The system MUST preserve read compatibility for historical completion-state aliases while using canonical names for new writes.

#### Scenario: attempt audit writes a waiting completion state

- **WHEN** new audit/protocol artifacts are materialized for `waiting_user` or `waiting_auth`
- **THEN** the written completion state MUST use canonical names
- **AND** protocol readers MAY continue to accept historical aliases for existing data

