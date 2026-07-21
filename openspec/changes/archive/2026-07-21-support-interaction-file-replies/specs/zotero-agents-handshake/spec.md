## MODIFIED Requirements

### Requirement: Backend MUST expose Zotero Agents handshake capability

The system MUST expose `POST /v1/system/handshake` for Zotero Agents clients to discover backend execution protocol support before submitting tasks.

#### Scenario: job protocol is supported
- **WHEN** a client calls `POST /v1/system/handshake` requesting `skillrunner.job.v1`
- **THEN** the response schema is `zotero-agents.skillrunner-handshake.response.v1`
- **AND** `backend.name` is `Skill-Runner`
- **AND** `backend.version` is the current backend version
- **AND** `protocols.skillrunner.job.v1.supported` is `true`

#### Scenario: interaction file protocol is supported when requested
- **WHEN** a client explicitly requests `skillrunner.interaction-files.v1`
- **THEN** `protocols.skillrunner.interaction-files.v1.supported` is `true`
- **AND** the protocol object contains the effective `max_files`, `max_file_bytes`, and `max_total_bytes`

#### Scenario: interaction file protocol is not requested
- **WHEN** an existing client does not request `skillrunner.interaction-files.v1`
- **THEN** the endpoint preserves the legacy default protocol set and response shapes
- **AND** it does not add the interaction file protocol to that response

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

## ADDED Requirements

### Requirement: Interaction file capability advertising MUST match enforcement policy
The system MUST obtain all advertised interaction file limits from the same effective server policy object used by multipart upload validation. Configured values MUST be positive and MUST NOT exceed the v1 protocol maxima of 8 files, 33,554,432 bytes per file, and 67,108,864 total bytes.

#### Scenario: Server configures lower limits
- **WHEN** the server configures valid interaction file limits below the protocol maxima
- **THEN** the handshake advertises those exact lower values
- **AND** the upload service enforces the same values

#### Scenario: Server configures invalid limits
- **WHEN** any configured limit is non-positive or exceeds its v1 protocol maximum
- **THEN** server configuration validation fails instead of advertising or silently clamping a different value
