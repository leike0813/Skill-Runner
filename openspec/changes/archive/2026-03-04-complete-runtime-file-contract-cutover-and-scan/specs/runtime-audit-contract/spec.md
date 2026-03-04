## ADDED Requirements

### Requirement: Request Input Snapshot Lives Under Audit

Request input snapshots for new runs MUST be written to `.audit/request_input.json`.

#### Scenario: a run is created from a request
- **WHEN** the request snapshot is persisted for audit
- **THEN** it is written to `.audit/request_input.json`
- **AND** no root-level `input.json` is written

### Requirement: Audit Files Are History Only

Audit files MUST be treated as history-only artifacts.

#### Scenario: parser diagnostics are emitted
- **WHEN** `.audit/parser_diagnostics.<attempt>.jsonl` is written
- **THEN** diagnostics are available for debugging
- **AND** they do not override current state or dispatch truth
