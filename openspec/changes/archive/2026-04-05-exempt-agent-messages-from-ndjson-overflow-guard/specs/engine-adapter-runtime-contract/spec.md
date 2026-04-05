## MODIFIED Requirements

### Requirement: Stream parsers MUST support incremental live parsing

The system MUST provide a live parser session contract so engine-specific parsers can emit semantic events incrementally during execution.

#### Scenario: overflowed non-message NDJSON line is repaired before semantic parsing

- **WHEN** a live NDJSON parser session observes a single logical line whose buffered size exceeds `4096` bytes before the terminating newline
- **AND** that logical line is not semantically classified as `agent.reasoning` or `agent.message`
- **THEN** it MUST stop retaining the full raw body in live memory
- **AND** it MUST attempt to repair the retained prefix into a valid JSON object when that line terminates or the process exits
- **AND** if repair succeeds, it MUST continue semantic parsing from the repaired object instead of dropping the line

#### Scenario: agent reasoning or message NDJSON line bypasses live truncation guard

- **WHEN** a live NDJSON parser session observes a logical line that is semantically classified as `agent.reasoning` or `agent.message`
- **AND** that line exceeds `4096` bytes before the terminating newline
- **THEN** the shared live buffer MUST NOT truncate or substitute that logical line solely because of the `4096` byte limit
- **AND** the engine-specific live parser MUST continue its normal semantic extraction from the full logical line

### Requirement: Runtime raw stream ingestion MUST preserve canonical protocol progress

系统 MUST 保证 runtime 对 subprocess stdout/stderr 的采集不会因为超长 NDJSON 单行而破坏后续协议推进。

#### Scenario: oversized non-message NDJSON stdout line is sanitized before audit persistence

- **WHEN** an NDJSON engine emits a single stdout logical line whose size exceeds `4096` bytes before the terminating newline
- **AND** that logical line is not semantically classified as `agent.reasoning` or `agent.message`
- **THEN** runtime ingress MUST stop retaining that line's full original body for downstream audit persistence
- **AND** it MUST sanitize the retained prefix into either a repaired JSON line or a runtime diagnostic JSON line before writing to runtime audit surfaces
- **AND** the original oversized body MUST NOT be written to `io_chunks` or `stdout.log`

#### Scenario: oversized agent reasoning or message line remains canonical raw truth

- **WHEN** runtime ingress receives an NDJSON logical line that is semantically classified as `agent.reasoning` or `agent.message`
- **AND** that logical line exceeds `4096` bytes before the terminating newline
- **THEN** runtime ingress MUST preserve that full logical line as the canonical raw truth for live parser, raw publisher, strict replay, and `raw_stdout`
- **AND** downstream runtime audit surfaces MUST NOT observe a truncated or substituted version of that line solely because of the `4096` byte limit

### Requirement: Sanitized overflow handling MUST preserve business semantics when possible

系统 MUST 优先保住超长 NDJSON 行的业务语义，而不是保留完整中间正文。

#### Scenario: agent reasoning or message classification is shared across live and audit paths

- **WHEN** runtime decides whether an oversized NDJSON logical line should be exempted from the `4096` byte overflow guard
- **THEN** live semantic parsing and runtime ingress sanitization MUST use the same semantic exemption decision
- **AND** the system MUST NOT allow live parsing to preserve the full line while audit/raw ingestion truncates the same line, or vice versa

#### Scenario: non-message oversized line continues using sanitized overflow path

- **WHEN** an oversized NDJSON line is classified as a non-message payload such as `tool_result`, `tool_call`, or `command_execution`
- **THEN** runtime MUST continue using the existing repair / sanitize / diagnostic substitution path
- **AND** overflow diagnostics such as `RUNTIME_STREAM_LINE_OVERFLOW_SANITIZED` and `RUNTIME_STREAM_LINE_OVERFLOW_DIAGNOSTIC_SUBSTITUTED` MUST continue to apply
