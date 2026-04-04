## MODIFIED Requirements

### Requirement: Runtime audit writing MUST NOT block the single-worker execution hot path

The system MUST ensure that runtime audit persistence does not synchronously block the main chunk-processing path of active runs.

#### Scenario: active run output is mirrored through background audit writers

- **WHEN** the runtime reads `stdout` / `stderr` chunks from an active subprocess
- **THEN** `stdout.log` / `stderr.log` / `io_chunks` MUST be persisted through background serial writers
- **AND** FCMP / RASP / chat replay audit mirrors MUST NOT perform per-event synchronous file writes on the main event loop hot path

#### Scenario: audit backpressure does not block live protocol publication

- **WHEN** an audit writer queue reaches its bounded capacity
- **THEN** the runtime MAY drop audit writes for that writer
- **AND** the system MUST continue prioritizing live journal publication and core protocol progression

### Requirement: Runtime auth detection MUST use low-frequency bounded windows

The system MUST avoid re-parsing the full accumulated runtime output on a high-frequency cadence while a run is active.

#### Scenario: active auth detection probes only recent output windows

- **WHEN** auth detection is enabled for an active run
- **THEN** the runtime MUST probe only recent bounded `stdout` / `stderr` windows
- **AND** it MUST NOT rebuild auth detection input by repeatedly joining the full historical output

#### Scenario: auth detection cadence is throttled

- **WHEN** a run is actively streaming output
- **THEN** auth detection probes MUST be throttled to a lower-frequency cadence than the previous `0.25s` path
- **AND** the runtime MUST still perform one final forced probe before process completion handling finishes

### Requirement: Slot release MUST remain decoupled from audit drain completion

The system MUST preserve current concurrency capacity semantics when introducing asynchronous audit writing.

#### Scenario: slot release does not wait for full audit drain

- **WHEN** the subprocess for a run attempt has exited and stream readers have completed
- **THEN** run slot release MUST NOT wait for full audit writer drain
- **AND** any terminal audit flush performed on the main lifecycle path MUST be bounded by a short best-effort budget

### Requirement: Terminal protocol history MUST avoid blocking on incomplete mirror drain

The system MUST keep terminal protocol/history reads responsive even if background audit mirrors are still draining.

#### Scenario: terminal protocol history falls back to live-first when bounded flush times out

- **WHEN** a terminal FCMP or RASP history request is served
- **AND** the bounded mirror flush does not finish within its budget
- **THEN** the system MUST return the currently available live protocol rows without synchronously waiting for audit completion
- **AND** the response shape and event schema MUST remain unchanged
