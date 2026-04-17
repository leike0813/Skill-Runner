# protocol-golden-fixture-framework Specification

## Purpose
TBD - created by archiving change protocol-golden-fixture-framework-foundation-2026-04-16. Update Purpose after archive.
## Requirements
### Requirement: protocol golden fixtures MUST have a machine-readable contract

Protocol-core golden fixtures MUST be described by a machine-readable contract that identifies fixture layer, engine scope, inputs, semantic expectations, normalization directives, and provenance.

#### Scenario: fixture corpus is loaded

- **WHEN** the golden fixture manifest is loaded
- **THEN** every referenced fixture MUST validate against the shared golden fixture contract
- **AND** every fixture MUST declare `fixture_id`, `layer`, `engine`, `inputs`, `expected`, `source`, and `capability_requirements`

### Requirement: fixture execution MUST be capability-gated

Golden fixtures MUST gate execution using the parser capability SSOT instead of inferring support from test names or implementation details.

#### Scenario: engine does not advertise required capability

- **WHEN** a fixture declares one or more capability requirements
- **AND** the target engine does not satisfy them in `runtime_parser_capabilities.yaml`
- **THEN** the framework MUST treat that fixture as unsupported for that engine
- **AND** it MUST NOT report the mismatch as a protocol regression

### Requirement: golden comparisons MUST normalize unstable protocol fields

Golden fixture comparison MUST remove or ignore unstable protocol fields before semantic comparison.

#### Scenario: protocol events contain volatile metadata

- **WHEN** RASP, FCMP, or outcome payloads are prepared for golden comparison
- **THEN** timestamps, sequence counters, raw byte offsets, and volatile run/request identifiers MUST be normalized according to fixture rules
- **AND** semantic protocol fields MUST remain available for assertion

### Requirement: semantic assertion helpers MUST support protocol-core expectations

The golden fixture framework MUST provide semantic assertion helpers for protocol-core behavior rather than requiring byte-for-byte snapshots.

#### Scenario: protocol-core smoke fixture is asserted

- **WHEN** a golden fixture declares expected RASP events, FCMP events, diagnostics, or outcome fields
- **THEN** the framework MUST support event presence and absence checks
- **AND** it MUST support ordering subsequence checks
- **AND** it MUST support partial semantic field matching for diagnostics and outcome data

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

### Requirement: captured-run golden fixtures MUST drive engine integration coverage

Captured-run golden fixtures MUST be executable through the engine integration test surface rather than living only in unit smoke tests.

#### Scenario: engine integration replay is executed

- **WHEN** engine integration tests are run
- **THEN** they MUST enumerate captured-run `protocol_core` and `outcome_core` fixtures from the golden manifest
- **AND** they MUST assert current protocol/outcome semantics using the shared golden replay harness

### Requirement: engine integration entrypoints MUST no longer depend on YAML suites as their primary truth source

Engine integration entrypoints MUST use the golden fixture corpus as their primary truth source.

#### Scenario: compatibility runner is invoked

- **WHEN** the engine integration compatibility runner is executed
- **THEN** it MUST dispatch to pytest-based golden integration tests
- **AND** it MUST NOT depend on `tests/engine_integration/suites/*.yaml` for engine integration case selection
- **AND** legacy suites MAY remain in the repository only for other consumers such as E2E

