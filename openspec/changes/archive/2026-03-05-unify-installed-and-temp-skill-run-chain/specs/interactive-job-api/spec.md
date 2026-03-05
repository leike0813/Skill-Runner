## ADDED Requirements

### Requirement: Jobs API MUST support unified request source

`POST /v1/jobs` MUST support a unified request source contract for installed skill and temp upload skill.

#### Scenario: create installed request from unified endpoint
- **WHEN** client calls `POST /v1/jobs` with `skill_source=installed` and `skill_id`
- **THEN** system MUST create request in unified request store
- **AND** response MUST return `request_id`

#### Scenario: create temp-upload request from unified endpoint
- **WHEN** client calls `POST /v1/jobs` with `skill_source=temp_upload`
- **THEN** system MUST create request in unified request store
- **AND** response MUST return `request_id`

### Requirement: Upload entry MUST be unified under jobs API

System MUST use `POST /v1/jobs/{request_id}/upload` as the only upload entry for both installed and temp-upload requests.

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

### Requirement: Legacy temp-skill-runs API MUST be removed

System MUST remove `/v1/temp-skill-runs/*` routes after unified jobs entry is active.

#### Scenario: temp-skill-runs endpoint is unavailable
- **WHEN** client calls any `/v1/temp-skill-runs/*` endpoint
- **THEN** system MUST return endpoint-not-found behavior
