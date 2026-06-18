# management-api-surface Delta

## ADDED Requirements

### Requirement: Engine management summaries MUST use non-blocking cached status
Engine management and UI summaries MUST not depend on synchronous SQLite reads in request handling.

#### Scenario: Client lists engines while SQLite is busy
- **WHEN** a client calls engine management or UI engine list endpoints
- **THEN** the service returns from in-memory engine status/cache data
- **AND** SQLite persistence failure only degrades engine version freshness
- **AND** unrelated endpoints such as system ping remain responsive
