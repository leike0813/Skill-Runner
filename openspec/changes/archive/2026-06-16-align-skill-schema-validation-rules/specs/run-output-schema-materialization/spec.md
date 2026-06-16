## MODIFIED Requirements

### Requirement: 每个 run MUST materialize 稳定 output schema artifact
The system MUST require a valid business `output` schema before runtime execution preparation and MUST materialize a stable run-scoped target output schema artifact pair under `.audit/contracts/`.

#### Scenario: auto run materializes final wrapper schema
- **WHEN** a skill run has a valid business `output.schema.json`
- **AND** execution mode is `auto`
- **THEN** the run MUST write `.audit/contracts/target_output_schema.json`
- **AND** that schema MUST require explicit `__SKILL_DONE__ = true`
- **AND** the business schema constraints MUST remain preserved in the materialized final wrapper

#### Scenario: interactive run materializes union schema
- **WHEN** a skill run has a valid business `output.schema.json`
- **AND** execution mode is `interactive`
- **THEN** the run MUST write `.audit/contracts/target_output_schema.json`
- **AND** that schema MUST contain both final and pending branches
- **AND** the pending branch MUST require `__SKILL_DONE__ = false`, `message`, and object `ui_hints`

#### Scenario: runtime preparation rejects missing output schema
- **WHEN** a skill does not resolve a valid business output schema
- **THEN** runtime execution preparation MUST fail before adapter execution

#### Scenario: runtime preparation accepts missing input and parameter schemas
- **WHEN** a skill resolves a valid business output schema
- **AND** `input` or `parameter` schemas are absent
- **THEN** runtime execution preparation MUST continue
