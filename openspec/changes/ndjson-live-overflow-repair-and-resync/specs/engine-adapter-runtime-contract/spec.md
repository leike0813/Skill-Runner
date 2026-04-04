## MODIFIED Requirements

### Requirement: Stream parsers MUST support incremental live parsing

The system MUST provide a live parser session contract so engine-specific parsers can emit semantic events incrementally during execution.

#### Scenario: overflowed NDJSON line is repaired before semantic parsing

- **WHEN** a live NDJSON parser session observes a single logical line whose buffered size exceeds `4096` bytes before the terminating newline
- **THEN** it MUST stop retaining the full raw body in live memory
- **AND** it MUST attempt to repair the retained prefix into a valid JSON object when that line terminates or the process exits
- **AND** if repair succeeds, it MUST continue semantic parsing from the repaired object instead of dropping the line

#### Scenario: repaired overflow line preserves semantic event type

- **WHEN** an overflowed line is successfully repaired into a valid JSON object
- **THEN** the engine-specific live parser MUST continue using its normal row handler on that repaired object
- **AND** the resulting `LiveParserEmission` values MUST preserve the semantic event type implied by the original payload shape
- **AND** associated `raw_ref.byte_from/byte_to` MUST still reference the true original byte span of the long line

#### Scenario: unrecoverable overflow line does not block later live events

- **WHEN** an overflowed line cannot be repaired into a valid JSON object
- **THEN** the live path MUST emit a diagnostic warning for that line
- **AND** it MUST discard only that line's semantic publication
- **AND** it MUST resume normal parsing at the next newline boundary without stalling later rows

### Requirement: Live parser emission order MUST define canonical RASP order

系统 MUST 将 live parser session 的 emission 顺序定义为 canonical RASP 顺序；audit mirror、batch backfill 和 replay 路径 MUST NOT 改写该顺序。

#### Scenario: repaired overflow warnings precede repaired semantic events

- **WHEN** a long NDJSON line is repaired and yields both a diagnostic warning and one or more semantic emissions
- **THEN** the warning emission MUST be published before the repaired semantic emissions for that same line
- **AND** subsequent rows MUST retain their original live order after that repaired line
