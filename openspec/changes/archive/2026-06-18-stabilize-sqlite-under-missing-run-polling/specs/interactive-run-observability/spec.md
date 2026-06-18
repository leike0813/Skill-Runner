# interactive-run-observability Delta

## ADDED Requirements

### Requirement: Missing run observability endpoints MUST remain cheap 404 responses
Observability endpoints for missing requests or missing runs MUST continue returning 404 and MUST NOT create SSE streams, placeholder requests, or placeholder run records.

#### Scenario: Events history is polled for a missing request
- **WHEN** a client calls `GET /v1/jobs/{request_id}/events/history` for an unknown request
- **THEN** the response status is 404
- **AND** no run directory, request row, or SSE stream is created.

#### Scenario: Chat history is polled for a missing request
- **WHEN** a client calls `GET /v1/jobs/{request_id}/chat/history` for an unknown request
- **THEN** the response status is 404
- **AND** no run directory, request row, or SSE stream is created.

#### Scenario: Missing-run polling happens concurrently with management reads
- **WHEN** many missing-run history requests arrive concurrently
- **THEN** unrelated management read endpoints remain responsive
- **AND** the missing-run requests continue to return 404.
