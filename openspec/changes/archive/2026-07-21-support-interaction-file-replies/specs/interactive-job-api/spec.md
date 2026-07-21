## MODIFIED Requirements

### Requirement: Upload entry MUST be unified under jobs API

System MUST use `POST /v1/jobs/{request_id}/upload` as the only initial package or job-input upload entry for both installed and temp-upload requests. The interaction reply file adapter at `POST /v1/jobs/{request_id}/interaction/reply/files` is a continuation endpoint and MUST NOT replace or alter the initial upload contract.

#### Scenario: temp upload request accepts skill package
- **GIVEN** request source is `temp_upload`
- **WHEN** client uploads package via `POST /v1/jobs/{request_id}/upload`
- **THEN** system MUST validate and stage package in request lifecycle

#### Scenario: installed request accepts input upload
- **GIVEN** request source is `installed`
- **WHEN** client uploads input zip via `POST /v1/jobs/{request_id}/upload`
- **THEN** system MUST build input manifest and continue standard dispatch flow

#### Scenario: temp upload creates run from parsed manifest without installed registry lookup
- **GIVEN** request source is `temp_upload`
- **AND** backend has parsed a valid skill manifest from uploaded package
- **WHEN** upload flow creates run
- **THEN** run creation MUST use the parsed manifest directly
- **AND** MUST NOT require installed skill registry lookup for the uploaded skill id

#### Scenario: interaction file reply remains a continuation adapter
- **GIVEN** a request is waiting for an `upload_files` interaction
- **WHEN** a client submits files through the interaction reply file endpoint
- **THEN** the request MUST enter the existing canonical interaction reply flow
- **AND** the initial package or input upload state MUST NOT be used

## ADDED Requirements

### Requirement: Waiting-user file interactions MUST declare canonical slots
When a request is `waiting_user` with `pending.ui_hints.kind=upload_files`, the system MUST treat each `pending.ui_hints.files[].name` as the canonical slot key and each `required` flag as the binding requirement.

#### Scenario: Client obtains pending file slots
- **WHEN** a client reads the current pending `upload_files` interaction
- **THEN** it can construct bindings from the declared file names and required flags without inventing a second slot namespace

### Requirement: Multipart file replies MUST converge on the canonical reply lifecycle
The jobs API MUST adapt a valid multipart file request to a typed interaction response and call the same canonical reply acceptance used by ordinary JSON replies. Success MUST return the existing `InteractionReplyResponse` with `accepted=true`, `mode=interaction`, and `status=queued`.

#### Scenario: Successful file reply resumes once
- **WHEN** a valid file reply wins canonical acceptance
- **THEN** pending is cleared, one accepted event is published, the request moves to `queued`, and exactly one next attempt is scheduled

#### Scenario: Adapter fails before canonical acceptance
- **WHEN** multipart parsing, validation, streaming, or storage publication fails
- **THEN** pending remains unconsumed and no accepted event or resume is produced

### Requirement: Interaction file reply errors MUST be stable HTTP semantics
The file reply adapter MUST distinguish malformed requests, semantic validation, limits, missing requests, conflicts, and internal storage failures without exposing local paths or file bytes.

#### Scenario: Client-correctable file reply failure
- **WHEN** a request has malformed multipart or JSON, invalid metadata or bindings, empty files, or exceeded limits
- **THEN** the API returns 400, 422, or 413 according to the documented category and leaves the interaction pending

#### Scenario: Stale or conflicting file reply
- **WHEN** a request targets missing state, a stale interaction, a non-waiting run, or an idempotency mismatch
- **THEN** the API returns 404 or 409 consistently with canonical reply semantics
