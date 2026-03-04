# interactive-run-lifecycle Specification Delta

## ADDED Requirements

### Requirement: waiting states MUST use a single-consumer resume contract
The system MUST use one durable resume ownership path when leaving `waiting_auth` or `waiting_user`.

#### Scenario: duplicate resume contenders race on the same waiting run
- **GIVEN** callback completion, reconcile, and restart recovery observe the same resumable waiting run
- **WHEN** they attempt to resume the run concurrently
- **THEN** only one path wins the durable resume ticket
- **AND** the non-winners MUST NOT advance the run state a second time

### Requirement: waiting state applicability MUST follow conversation capability
The system MUST gate `waiting_auth` and real `waiting_user` by `client_metadata.conversation_mode`, not by `execution_mode` alone.

#### Scenario: session-capable auto run hits auth
- **GIVEN** a run uses `execution_mode=auto`
- **AND** `client_metadata.conversation_mode=session`
- **WHEN** high-confidence auth is detected
- **THEN** the run MAY enter `waiting_auth`

#### Scenario: non-session run hits auth
- **GIVEN** a run uses `client_metadata.conversation_mode=non_session`
- **WHEN** high-confidence auth is detected
- **THEN** the run MUST NOT enter `waiting_auth`
- **AND** the backend MUST preserve fail-fast auth behavior

#### Scenario: non-session interactive execution needs user reply
- **GIVEN** a run resolves to `execution_mode=interactive`
- **AND** `client_metadata.conversation_mode=non_session`
- **WHEN** the skill would otherwise require user reply
- **THEN** the backend MUST normalize execution to zero-timeout auto-reply
- **AND** the run MUST NOT expose a real `waiting_user` state

### Requirement: resumed execution MUST materialize exactly one target attempt
The system MUST determine and materialize exactly one target attempt before `turn.started`.

#### Scenario: waiting-state resume is accepted
- **GIVEN** a waiting run has an accepted resume ticket
- **WHEN** the resumed execution is scheduled
- **THEN** the system MUST determine `target_attempt` before `turn.started`
- **AND** the same resume flow MUST NOT emit more than one `lifecycle.run.started` for that attempt

### Requirement: waiting-state pending data MUST be attempt-scoped
The system MUST keep current pending data and append-only history in separate attempt-aware layers.

#### Scenario: a run transitions from waiting to a new attempt
- **GIVEN** a run leaves `waiting_user` or `waiting_auth`
- **WHEN** the system persists the current pending owner and historical interaction/auth rows
- **THEN** current pending data MUST represent only the live waiting owner
- **AND** history entries MUST retain the source attempt that produced them

### Requirement: restart recovery MUST preserve resume ownership semantics
Restart recovery MUST reuse the same canonical resume ownership contract as live callback/reconcile paths.

#### Scenario: service restarts while a run is resumable
- **GIVEN** the service restarts while a run has a resumable waiting state
- **WHEN** recovery reconciles the run
- **THEN** recovery MUST reuse the same durable resume ownership contract
- **AND** recovery MUST NOT create a second competing resume path
