# interactive-job-api Specification Delta

## ADDED Requirements

### Requirement: `interaction/reply` MUST support auth method selection
The `interaction/reply` request payload MUST support auth method selection and auth submission in `mode=auth`.

#### Scenario: client submits auth reply payload
- **GIVEN** a run is in `waiting_auth`
- **WHEN** the client submits `POST /interaction/reply` with `mode=auth`
- **THEN** the payload MUST support selecting auth method
- **AND** the payload MUST support auth submission content

### Requirement: 系统 MUST 提供 auth session 状态接口
The backend MUST provide `GET /v1/jobs/{run_id}/auth/session` for auth timeout and status synchronization.

#### Scenario: client queries auth session status
- **GIVEN** a run is waiting for authentication
- **WHEN** the client requests `GET /v1/jobs/{run_id}/auth/session`
- **THEN** the backend MUST return current auth session status
- **AND** the backend MUST return timeout-related fields

### Requirement: auth submission kinds MUST include callback URL
Auth submission kinds MUST include `callback_url`, `authorization_code`, and `api_key`.

#### Scenario: client submits auth input in chat
- **GIVEN** the client is submitting an auth response through chat
- **WHEN** the backend validates submission kind
- **THEN** it MUST accept `callback_url`
- **AND** it MUST accept `authorization_code` and `api_key`
