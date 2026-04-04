## MODIFIED Requirements

### Requirement: Protocol history queries MUST preserve live responsiveness for active runs

The system MUST avoid routing running protocol history requests through heavyweight audit reindex and full-file reads when a live journal already exists for the current attempt.

#### Scenario: running current-attempt FCMP history uses live-first hot path

- **WHEN** a `protocol/history` query requests `stream=fcmp` for a run whose status is `queued` or `running`
- **AND** the resolved attempt equals the current attempt
- **THEN** the service MUST return the FCMP history from the live journal hot path
- **AND** it MUST NOT require audit JSONL reads before returning
- **AND** it MUST NOT trigger FCMP global reindex on that hot path

#### Scenario: running current-attempt RASP history uses live-first hot path

- **WHEN** a `protocol/history` query requests `stream=rasp` for a run whose status is `queued` or `running`
- **AND** the resolved attempt equals the current attempt
- **THEN** the service MUST return the RASP history from the live journal hot path
- **AND** it MUST NOT require audit JSONL reads before returning

#### Scenario: non-current or terminal history keeps audit semantics

- **WHEN** a `protocol/history` query targets a terminal run or a non-current attempt
- **THEN** the service MAY continue using the existing audit-backed history path
- **AND** it MUST preserve the existing `protocol/history` response shape

### Requirement: Protocol history changes MUST NOT alter UI-facing stream contracts

The system MUST preserve existing UI and protocol contracts while optimizing the running hot path.

#### Scenario: running live-first history preserves response shape

- **WHEN** a running current-attempt FCMP or RASP history request is served from the live-first hot path
- **THEN** the response MUST still include `attempt`, `available_attempts`, `events`, `cursor_floor`, and `cursor_ceiling`
- **AND** it MUST remain compatible with the existing run detail UI polling logic without frontend changes
