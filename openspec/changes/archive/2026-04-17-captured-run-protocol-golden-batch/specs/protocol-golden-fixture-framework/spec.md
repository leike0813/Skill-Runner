## ADDED Requirements

### Requirement: protocol golden fixtures MUST support captured whole-run sources

The protocol golden fixture framework MUST support captured runs as first-class fixture sources for `protocol_core` and `outcome_core`.

#### Scenario: whole-run captured fixture is loaded

- **WHEN** a fixture declares `source: captured_run`
- **AND** it declares `capture_mode`, `attempts`, and `run_artifacts`
- **THEN** the contract loader MUST validate those fields
- **AND** the fixture MUST preserve `source_run_id`

### Requirement: captured protocol fixtures MUST assert stable run-level semantics

Captured `protocol_core` fixtures MUST assert stable run-level semantics rather than replaying historical event files as snapshots.

#### Scenario: multi-attempt waiting-user run is replayed

- **WHEN** a whole-run captured protocol fixture is executed
- **THEN** the harness MUST replay each attempt through the current protocol builder
- **AND** the fixture MUST assert semantic state transitions such as `waiting_user -> succeeded`
- **AND** it MUST avoid relying on unstable historical diagnostics or byte-for-byte event snapshots

### Requirement: captured outcome fixtures MUST assert terminal success-source semantics

Captured `outcome_core` fixtures MUST assert terminal result semantics derived from the captured run result and terminal metadata.

#### Scenario: captured outcome fixture is asserted

- **WHEN** a captured outcome fixture is executed
- **THEN** it MUST assert final status, result status, and `success_source`
- **AND** it MUST support semantic assertions for category-specific result fields, warnings, and artifacts
