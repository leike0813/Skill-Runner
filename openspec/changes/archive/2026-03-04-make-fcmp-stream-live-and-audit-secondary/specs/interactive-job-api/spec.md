## ADDED Requirements

### Requirement: Live SSE MUST consume published FCMP rather than materialized audit FCMP
The system MUST publish FCMP into a live journal first and MUST deliver active SSE traffic from that live publication path instead of reconstructing FCMP from audit files.

#### Scenario: terminal final message remains visible while audit mirror lags
- **GIVEN** an active or recently terminal run
- **AND** the final audit FCMP file has not been mirrored yet
- **WHEN** the client subscribes to `/events`
- **THEN** the client MUST still receive the published `assistant.message.final`
- **AND** the stream MUST NOT wait for `.audit/fcmp_events.*.jsonl` to appear

### Requirement: events/history MUST support memory-first replay with audit fallback
The system MUST replay active and recently terminal FCMP events from memory first and MUST fall back to audit only when the requested cursor falls outside the live retention window or live memory is unavailable.

#### Scenario: recent cursor replays from memory
- **WHEN** the client calls `/events/history` for a recent cursor on an active or recently terminal run
- **THEN** the response MAY use `source=live`
- **AND** MUST NOT require audit materialization first

#### Scenario: old cursor falls back to audit
- **WHEN** the requested cursor predates the live journal floor or the process has restarted
- **THEN** the response MAY use `source=audit` or `source=mixed`
- **AND** the replayed event order MUST remain FCMP `seq` order
