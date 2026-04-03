## MODIFIED Requirements

### Requirement: Stream parsers MUST support incremental live parsing

The system MUST provide a live parser session contract so engine-specific parsers can emit semantic events incrementally during execution.

#### Scenario: Claude emits run handle on system init without waiting for process exit

- **WHEN** Claude live parser session reads a complete `type=system` / `subtype=init` NDJSON row with a valid `session_id`
- **THEN** it MUST immediately emit `run_handle.handle_id = session_id`
- **AND** it MUST treat that same row as a valid `turn_marker:start` anchor

#### Scenario: Claude emits semantic rows incrementally in live order

- **WHEN** Claude live parser session reads complete NDJSON rows for assistant text, `tool_use`, `tool_result`, and `result`
- **THEN** it MUST emit the corresponding `LiveParserEmission` values during `feed()`
- **AND** emission order MUST follow the actual parser `feed()` row order
- **AND** it MUST NOT wait for batch materialization or process exit before publishing those semantics

#### Scenario: Claude batch parse remains backfill-only for active live publishing

- **WHEN** Claude live parser session has already published semantic output for an active run
- **THEN** `parse_runtime_stream()` MAY still be used for replay, backfill, and parity verification
- **AND** it MUST NOT redefine the live-authoritative semantic order for that active run
