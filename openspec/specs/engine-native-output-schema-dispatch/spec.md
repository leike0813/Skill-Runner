# engine-native-output-schema-dispatch Specification

## Purpose
TBD - created by archiving change agent-output-native-schema-engine-integration-phase2-2026-04-12. Update Purpose after archive.
## Requirements
### Requirement: Claude headless dispatch MUST consume the materialized output schema
Claude headless start/resume commands MUST consume the run-scoped materialized target output schema artifact when it is available.

#### Scenario: start command uses JSON output mode and schema path
- **WHEN** a Claude headless start command is built
- **AND** internal `run_options` include `__target_output_schema_relpath`
- **THEN** the command MUST include `--output-format json`
- **AND** it MUST include `--json-schema <run-relative-schema-path>`
- **AND** it MUST keep the existing prompt and effort semantics unchanged

#### Scenario: resume command reuses the same schema source
- **WHEN** a Claude headless resume command is built
- **AND** internal `run_options` include `__target_output_schema_relpath`
- **THEN** the command MUST include `--json-schema <run-relative-schema-path>`
- **AND** it MUST reuse the same schema path source as the start command

### Requirement: Codex headless dispatch MUST consume the materialized output schema
Codex headless start/resume commands MUST consume the run-scoped materialized target output schema artifact when it is available.

#### Scenario: start command includes output schema file
- **WHEN** a Codex headless start command is built
- **AND** internal `run_options` include `__target_output_schema_relpath`
- **THEN** the command MUST include `--output-schema <run-relative-schema-path>`
- **AND** it MUST preserve the existing `exec` command structure and approval-mode semantics

#### Scenario: resume command includes output schema file
- **WHEN** a Codex headless resume command is built
- **AND** internal `run_options` include `__target_output_schema_relpath`
- **THEN** the command MUST include `--output-schema <run-relative-schema-path>`
- **AND** it MUST reuse the same schema path source as the start command

### Requirement: Native schema dispatch MUST preserve passthrough and audit behavior
Native schema integration MUST not take ownership away from passthrough dispatch, and injected flags MUST remain observable through first-attempt command audit.

#### Scenario: passthrough commands remain unchanged
- **WHEN** a builder receives explicit passthrough CLI args
- **THEN** it MUST NOT inject native schema flags automatically

#### Scenario: first-attempt spawn command audit shows injected schema flags
- **WHEN** a first-attempt Claude or Codex headless run launches with a materialized schema relpath
- **THEN** the first-attempt spawn command audit MUST record the injected native schema argument in the observed command

