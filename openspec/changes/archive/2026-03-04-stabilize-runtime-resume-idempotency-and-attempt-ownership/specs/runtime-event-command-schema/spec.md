# runtime-event-command-schema Specification Delta

## ADDED Requirements

### Requirement: runtime protocol payloads MUST expose resume ownership metadata
The runtime protocol schema MUST support resume ownership metadata without breaking backward compatibility.

#### Scenario: resume-related FCMP or orchestrator payload is emitted
- **GIVEN** the system emits resume-related FCMP or orchestrator payloads
- **WHEN** the payload is validated against the runtime schema
- **THEN** it MUST support `resume_cause`, `pending_owner`, `source_attempt`, `target_attempt`, `resume_ticket_id`, and `ticket_consumed`
- **AND** these fields MUST remain optional for backward compatibility

### Requirement: pending and history payloads MUST preserve attempt attribution
Pending and history payloads MUST carry attempt attribution in schema-supported fields.

#### Scenario: pending interaction or interaction history row is written
- **GIVEN** the system writes pending interaction or interaction history payloads
- **WHEN** the payload is validated
- **THEN** the schema MUST support `source_attempt`
- **AND** read paths MUST continue to tolerate legacy rows that predate this field

### Requirement: protocol and read-model schemas MUST not encode conversation capability by state name
Schema contracts MUST let clients read effective runtime behavior without inferring it from `waiting_auth`.

#### Scenario: client inspects waiting-state payloads
- **GIVEN** the backend emits waiting-state protocol payloads or status/read-model responses
- **WHEN** the client needs to decide whether a run is session-capable
- **THEN** the contract MUST expose explicit conversation capability fields on read-model/status surfaces
- **AND** `waiting_auth` MUST NOT imply `interactive`
