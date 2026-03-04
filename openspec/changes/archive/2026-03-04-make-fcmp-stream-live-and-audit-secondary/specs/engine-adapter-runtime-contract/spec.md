## ADDED Requirements

### Requirement: Adapters MUST expose chunk-level runtime output during execution
The system MUST require runtime adapters to expose stdout/stderr chunks while the subprocess is still running, so the protocol layer can publish live events without waiting for post-hoc audit reconstruction.

#### Scenario: chunk output is forwarded to the live emitter
- **WHEN** the adapter reads a stdout or stderr chunk from a running engine process
- **THEN** it MUST forward that chunk to the live runtime emitter before process completion

### Requirement: Stream parsers MUST support incremental live parsing
The system MUST provide a live parser session contract so engine-specific parsers can emit semantic events incrementally during execution.

#### Scenario: parser session emits semantic output before audit mirror
- **WHEN** a parser can identify a complete semantic runtime event from incoming chunks
- **THEN** it MUST be able to emit that event through the live parser session
- **AND** the resulting FCMP / RASP publication MUST NOT wait for audit materialization

### Requirement: Batch parse MUST remain secondary and backfill-only
The system MAY retain batch parse utilities for backfill, cold replay, and parity testing, but MUST NOT use batch materialization as the live-authoritative source for SSE.

#### Scenario: active SSE does not require batch materialization
- **WHEN** an active run has published live events
- **THEN** the SSE path MUST serve those events directly
- **AND** MUST NOT invoke batch FCMP/RASP materialization as a prerequisite
