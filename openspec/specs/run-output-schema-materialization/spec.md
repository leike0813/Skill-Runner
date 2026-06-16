# run-output-schema-materialization Specification

## Purpose
TBD - created by archiving change agent-output-schema-builder-materialization-2026-04-12. Update Purpose after archive.
## Requirements
### Requirement: 每个 run MUST materialize 稳定 output schema artifact
The system MUST materialize a stable run-scoped target output schema artifact pair under `.audit/contracts/`.

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

#### Scenario: missing output schema skips materialization
- **WHEN** a skill does not resolve a valid business output schema
- **THEN** the builder MUST return an empty materialization result
- **AND** it MUST NOT write target output schema artifacts

### Requirement: materialized schema MUST be reusable by audit and execution plumbing
The run-scoped schema artifact paths MUST be stable and reusable across dispatch, execution, and resume.

#### Scenario: run options expose stable relative paths
- **WHEN** target output schema artifacts exist for a run
- **THEN** internal `run_options` MUST expose stable run-relative paths for the machine schema and prompt summary artifacts

#### Scenario: request input snapshot records first-attempt schema paths
- **WHEN** the request-input audit snapshot exists during materialization
- **THEN** it MUST record first-attempt fields for the materialized machine schema path and prompt summary path

### Requirement: Final wrapper materialization MUST preserve object-union branch semantics

When a business output schema is an object schema containing `oneOf` or `anyOf`, runtime MUST preserve that union while adding the Skill Runner completion marker.

#### Scenario: Object-union output schema receives completion marker in every branch
- **GIVEN** a business output schema has root `type=object`
- **AND** it contains `oneOf` or `anyOf` object branches
- **WHEN** the final wrapper schema is materialized
- **THEN** the schema root requires `__SKILL_DONE__=true`
- **AND** each object branch also allows and requires `__SKILL_DONE__=true`
- **AND** branch schemas with `additionalProperties=false` can validate a final payload containing the marker

#### Scenario: Non-object schema keeps legacy result wrapper
- **GIVEN** a business output schema does not declare root `type=object`
- **WHEN** the final wrapper schema is materialized
- **THEN** runtime continues to wrap the business payload under `result`

