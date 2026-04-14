## ADDED Requirements

### Requirement: Attempt audit MUST preserve quarantined overflow raw lines

Attempt-scoped audit assets MUST preserve the original decoded text of overflowed non-message NDJSON
logical lines in dedicated sidecar files.

#### Scenario: overflow index points to per-line raw sidecar

- **WHEN** runtime quarantines an overflowed non-message NDJSON logical line during attempt `N`
- **THEN** it MUST append a record to `.audit/overflow_index.N.jsonl`
- **AND** that record MUST include `overflow_id`, `attempt_number`, `stream`, `line_start_byte`, `total_bytes`, `sha256`, `disposition`, `diagnostic_code`, `raw_relpath`, `head_preview`, and `tail_preview`
- **AND** the referenced raw sidecar file MUST exist under `.audit/overflow_lines/N/`

#### Scenario: normal hot-path audit files remain sanitized

- **WHEN** runtime quarantines an overflowed non-message NDJSON logical line
- **THEN** `.audit/stdout.N.log`, `.audit/pty-output.N.log`, and `.audit/io_chunks.N.jsonl` MUST continue to store only the sanitized row or diagnostic stub
- **AND** they MUST NOT duplicate the full quarantined raw line body
