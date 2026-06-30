## ADDED Requirements

### Requirement: Backend MUST expose Zotero Agents handshake capability

The system MUST expose `POST /v1/system/handshake` for Zotero Agents clients to discover backend execution protocol support before submitting tasks.

#### Scenario: job protocol is supported
- **WHEN** a client calls `POST /v1/system/handshake` requesting `skillrunner.job.v1`
- **THEN** the response schema is `zotero-agents.skillrunner-handshake.response.v1`
- **AND** `backend.name` is `Skill-Runner`
- **AND** `backend.version` is the current backend version
- **AND** `protocols.skillrunner.job.v1.supported` is `true`

#### Scenario: sequence protocol is not yet supported
- **WHEN** a client requests `skillrunner.sequence.v1`
- **THEN** the response includes `protocols.skillrunner.sequence.v1.supported=false`

#### Scenario: unknown protocols are safe
- **WHEN** a client requests an unknown protocol id
- **THEN** the endpoint does not return 500
- **AND** the unknown protocol is either omitted or returned with `supported=false`

#### Scenario: ping remains reachability-only
- **WHEN** a client calls `GET /v1/system/ping` or `HEAD /v1/system/ping`
- **THEN** the response remains `204 No Content`
- **AND** the endpoint does not express protocol capabilities

### Requirement: Protocol ids MUST be stable contracts

The system MUST treat protocol ids returned by handshake as stable contracts.

#### Scenario: protocol semantics change
- **WHEN** a future backend adds incompatible protocol semantics
- **THEN** it MUST introduce a new protocol id
- **AND** it MUST NOT reuse an existing id with changed behavior

### Requirement: Handshake auth policy MUST match management system endpoints

The handshake endpoint MUST follow the same authentication policy as current management/system endpoints.

#### Scenario: UI Basic Auth is enabled
- **WHEN** UI Basic Auth is enabled
- **THEN** `POST /v1/system/handshake` remains accessible according to the management/system policy
