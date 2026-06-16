## MODIFIED Requirements

### Requirement: Management run observability aliases MUST inherit pre-observable read behavior
Management event and chat aliases MUST preserve Jobs API pre-observable semantics.

#### Scenario: Management history aliases for pre-observable request
- **GIVEN** a request exists
- **AND** no `run_id` has been bound yet
- **WHEN** the client calls management `/events/history` or `/chat/history`
- **THEN** the system returns `200`
- **AND** the response contains no events
- **AND** `source=pre_observable`
