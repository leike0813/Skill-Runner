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

