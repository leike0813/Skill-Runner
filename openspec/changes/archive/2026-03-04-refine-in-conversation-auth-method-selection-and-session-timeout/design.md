# Design: refine-in-conversation-auth-method-selection-and-session-timeout

## Summary

Keep `waiting_auth` as the canonical state, but split its internal orchestration into two phases:

- `method_selection`
- `challenge_active`

Only `challenge_active` owns a concrete auth session and therefore owns timeout.

## Core Decisions

### 1. No capability negotiation

This change does not introduce client capability negotiation and does not infer locality from request metadata.
Method choice is explicit and user-driven.

### 2. Method and submission are different layers

Auth methods:

- `callback`
- `device_auth`
- `authorization_code`
- `api_key`

Chat submission kinds:

- `callback_url`
- `authorization_code`
- `api_key`

Backend-only mapping:

- `callback_url -> text`
- `authorization_code -> code`
- `api_key -> api_key`

### 3. Session-scoped timeout

Timeout starts only after a concrete auth session is created.
`method_selection` does not consume timeout budget.
Backend remains the only timeout truth source through `created_at`, `expires_at`, `timeout_sec`, `server_now`, and `timed_out`.

### 4. Method matrix

Fixed first-wave matrix:

- `codex`: `callback`, `device_auth`
- `gemini`: `callback`, `authorization_code`
- `iflow`: `callback`, `authorization_code`
- `opencode + openai`: `callback`, `device_auth`
- `opencode + google`: `callback`
- `opencode + api-key-only providers`: `api_key`

### 5. Busy behavior

If an auth session is already active and blocks a new one:

- keep run in `waiting_auth`
- surface explicit error in UI
- do not auto-fail and do not preempt the active session

## Data Model

### Pending auth selection

Run store persists:

- `pending_auth_method_selection`

Fields:

- `engine`
- `provider_id`
- `available_methods`
- `prompt`
- `instructions`
- `source_attempt`
- `phase="method_selection"`

### Pending auth challenge

Run store persists:

- `pending_auth`

Extended fields:

- `phase="challenge_active"`
- `auth_method`
- `challenge_kind`
- `input_kind`
- `timeout_sec`
- `created_at`
- `expires_at`

### Auth session status response

The new `GET /v1/jobs/{run_id}/auth/session` endpoint returns the backend-authored session truth:

- `phase`
- `waiting_auth`
- `timed_out`
- `available_methods`
- `selected_method`
- `auth_session_id`
- `challenge_kind`
- `timeout_sec`
- `created_at`
- `expires_at`
- `server_now`
- `last_error`

## Integration Points

### Orchestration

`run_auth_orchestration_service` becomes the canonical run-scoped coordinator for:

- available-method resolution
- method selection persistence
- auth session creation
- submission-kind mapping
- session status reading
- timeout handling
- switching methods
- auth completion resume scheduling

### API

`POST /v1/jobs/{run_id}/interaction/reply` for `mode=auth` becomes a union:

- auth method selection
- auth submission

New endpoint:

- `GET /v1/jobs/{run_id}/auth/session`

### Frontend

The same reply area switches widget mode by backend hint:

- `choice` for method selection
- `text` for callback URL / authorization code / API key

`device_auth` shows link/user code and disables text submission.

## Security

Raw secrets must never enter:

- `.audit/meta`
- parser diagnostics
- FCMP history
- SSE payload history
- persisted chat messages

Only redacted submission metadata may be stored.
