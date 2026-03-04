# session-runtime-statechart-ssot Specification Delta

## ADDED Requirements

### Requirement: waiting-state applicability MUST follow execution-mode and conversation-mode matrix
The canonical runtime statechart MUST treat `execution_mode` and `client_metadata.conversation_mode` as orthogonal inputs.

#### Scenario: session-capable auto run hits auth
- **GIVEN** a run uses `execution_mode=auto`
- **AND** `client_metadata.conversation_mode=session`
- **WHEN** high-confidence auth is detected
- **THEN** the canonical statechart MUST allow `running -> waiting_auth`

#### Scenario: session-capable interactive run needs user reply
- **GIVEN** a run uses `execution_mode=interactive`
- **AND** `client_metadata.conversation_mode=session`
- **WHEN** the turn requires user reply
- **THEN** the canonical statechart MUST allow `running -> waiting_user`

#### Scenario: non-session client cannot sustain waiting states
- **GIVEN** a run uses `client_metadata.conversation_mode=non_session`
- **WHEN** the turn would otherwise require auth or user reply
- **THEN** the backend MUST NOT expose real `waiting_auth` or `waiting_user`
- **AND** non-session interactive execution MUST be normalized to zero-timeout auto-reply when needed
