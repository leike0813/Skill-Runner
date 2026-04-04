## MODIFIED Requirements

### Requirement: Runtime raw stream ingestion MUST preserve canonical protocol progress

系统 MUST 保证 runtime 对 subprocess stdout/stderr 的采集不会因为超长 NDJSON 单行而破坏后续协议推进。

#### Scenario: oversized NDJSON stdout line is sanitized before audit persistence

- **WHEN** an NDJSON engine emits a single stdout logical line whose size exceeds `4096` bytes before the terminating newline
- **THEN** runtime ingress MUST stop retaining that line's full original body for downstream audit persistence
- **AND** it MUST sanitize the retained prefix into either a repaired JSON line or a runtime diagnostic JSON line before writing to runtime audit surfaces
- **AND** the original oversized body MUST NOT be written to `io_chunks` or `stdout.log`

#### Scenario: sanitized runtime raw becomes downstream single source of truth

- **WHEN** runtime ingress sanitizes an oversized NDJSON stdout line
- **THEN** the sanitized line MUST become the input seen by live parser, raw publisher, strict replay, and `raw_stdout`
- **AND** downstream components MUST NOT observe the dropped original oversized body through normal runtime audit reads

### Requirement: Sanitized overflow handling MUST preserve business semantics when possible

系统 MUST 优先保住超长 NDJSON 行的业务语义，而不是保留完整中间正文。

#### Scenario: oversized tool_result line is repaired into valid JSON

- **WHEN** an oversized NDJSON line can be repaired into a valid JSON object from its retained prefix
- **THEN** runtime MUST emit that repaired JSON line as the sanitized raw row
- **AND** downstream engine-specific parsers MUST continue normal semantic extraction from that repaired object
- **AND** runtime MUST emit a diagnostic warning with code `RUNTIME_STREAM_LINE_OVERFLOW_SANITIZED`

#### Scenario: unrecoverable oversized line is substituted with runtime diagnostic JSON

- **WHEN** an oversized NDJSON line cannot be repaired into a valid JSON object
- **THEN** runtime MUST substitute a runtime diagnostic JSON line in place of the original row
- **AND** runtime MUST emit a diagnostic warning with code `RUNTIME_STREAM_LINE_OVERFLOW_DIAGNOSTIC_SUBSTITUTED`
- **AND** later logical lines in the same stream MUST continue normal runtime parsing and publication
