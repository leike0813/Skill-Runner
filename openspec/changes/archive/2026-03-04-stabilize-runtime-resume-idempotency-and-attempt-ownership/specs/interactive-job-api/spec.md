# interactive-job-api Specification Delta

## ADDED Requirements

### Requirement: pending and auth status APIs MUST surface current waiting owner
The backend MUST expose the current waiting owner for reconciliation-safe clients.

#### Scenario: client reads pending interaction or auth session status
- **GIVEN** a client reads pending interaction or auth session status
- **WHEN** the run is in a waiting state
- **THEN** the backend MUST expose which current waiting owner is active
- **AND** the response SHOULD expose resume ownership metadata needed for reconciliation-safe refresh

### Requirement: run APIs MUST expose effective execution behavior
The backend MUST expose requested mode, effective mode, and client conversation capability separately.

#### Scenario: client reads status for a normalized run
- **GIVEN** a run request has client-declared conversation metadata
- **WHEN** the backend returns status, pending, or auth-session truth
- **THEN** the response MUST expose requested and effective execution behavior separately
- **AND** the response MUST expose `conversation_mode`
- **AND** clients MUST NOT infer conversation capability from `waiting_auth` or `waiting_user` state names alone

### Requirement: resumed interactive execution MUST expose target-attempt semantics
The backend MUST expose resumed execution as `waiting_* -> queued` followed by a single target-attempt start.

#### Scenario: backend accepts a reply-driven or auth-driven resume
- **GIVEN** the backend accepts a reply-driven or auth-driven resume
- **WHEN** the API-visible state changes are emitted
- **THEN** the transition MUST represent `waiting_* -> queued` first
- **AND** the next `queued -> running` transition MUST correspond to exactly one target attempt

### Requirement: terminal status reads MUST NOT be inferred from stale waiting payloads
API and UI consumers MUST treat terminal status/result as the only terminal truth.

#### Scenario: run reaches a terminal state
- **GIVEN** a run reaches `failed`, `canceled`, or `succeeded`
- **WHEN** API or UI consumers render the terminal result
- **THEN** they MUST read terminal truth from terminal status/result
- **AND** they MUST NOT infer terminal completion from stale pending or history payloads
