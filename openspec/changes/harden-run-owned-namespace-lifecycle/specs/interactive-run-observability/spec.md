# interactive-run-observability Delta

## MODIFIED Requirements

### Requirement: terminal protocol history MUST converge to audit-only source
Terminal protocol history MUST read the request-owned audit directory first for request-bound runs.

#### Scenario: Terminal protocol history prefers namespaced audit
- **GIVEN** a terminal request-bound run has `.audit/<namespace>/fcmp_events.<attempt>.jsonl` or `.audit/<namespace>/events.<attempt>.jsonl`
- **WHEN** `protocol/history` is requested
- **THEN** the response is built from the namespaced audit files
- **AND** root `.audit` files are not preferred over namespaced files.

#### Scenario: Split historical run remains observable
- **GIVEN** a historical or in-flight split run has empty namespaced protocol mirrors
- **AND** root `.audit` protocol mirrors contain rows
- **WHEN** `protocol/history` or chat history is requested
- **THEN** the service may include root audit rows as compatibility fallback
- **AND** the fallback does not make root audit the preferred target for new writes.

### Requirement: 日志轮询建议 MUST 区分 waiting_user 与 running
Logs tail MUST read stdout and stderr from the request-owned audit directory before deciding polling behavior.

#### Scenario: Logs tail reads namespaced attempt logs
- **GIVEN** a request-bound run has attempt logs under `.audit/<namespace>/`
- **WHEN** a client reads logs tail or logs response
- **THEN** stdout and stderr are read from `.audit/<namespace>/stdout.<attempt>.log` and `.audit/<namespace>/stderr.<attempt>.log`
- **AND** root `.audit` logs are fallback only for no-layout or legacy runs.

## ADDED Requirements

### Requirement: Chat and event history MUST be layout-aware
Event and chat history endpoints MUST resolve the request layout before reading persisted history.

#### Scenario: Event history reads namespaced audit
- **WHEN** a client reads event history for a request-bound run with layout metadata
- **THEN** the service reads `.audit/<namespace>/events.<attempt>.jsonl`, `.audit/<namespace>/fcmp_events.<attempt>.jsonl`, and `.audit/<namespace>/orchestrator_events.<attempt>.jsonl` as applicable.

#### Scenario: Chat history reads namespaced replay
- **WHEN** a client reads chat history for a request-bound run with layout metadata
- **THEN** the service reads `.audit/<namespace>/chat_replay.jsonl`
- **AND** may derive missing chat rows from namespaced FCMP rows.
