# interactive-run-lifecycle Specification Delta

## ADDED Requirements

### Requirement: `waiting_auth` MUST support internal phases
The system MUST represent `waiting_auth` with explicit internal phases: `method_selection` and `challenge_active`.

#### Scenario: run enters waiting_auth
- **GIVEN** a run enters `waiting_auth`
- **WHEN** pending auth payload and auth session status are read
- **THEN** phase MUST be explicitly readable
- **AND** phase MUST distinguish `method_selection` and `challenge_active`

### Requirement: `waiting_auth` timeout MUST be auth-session scoped
Auth timeout MUST be counted only for active auth sessions.

#### Scenario: phase changes from selection to challenge
- **GIVEN** a run is in `waiting_auth`
- **WHEN** phase is `method_selection`
- **THEN** auth timeout MUST NOT be counted
- **WHEN** phase is `challenge_active`
- **THEN** auth timeout MUST be enforced per auth session

### Requirement: busy auth session MUST keep run in `waiting_auth`
When active auth session blocks new session creation, run state MUST remain `waiting_auth`.

#### Scenario: auth session creation is blocked by active session
- **GIVEN** a run is waiting for auth
- **WHEN** a new auth session cannot be created due to an existing active session
- **THEN** run state MUST remain `waiting_auth`
- **AND** the client MUST receive an explicit error
