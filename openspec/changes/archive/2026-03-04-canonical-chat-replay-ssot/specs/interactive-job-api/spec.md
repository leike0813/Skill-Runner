## ADDED Requirements

### Requirement: Chat windows use canonical chat replay

User-facing interactive chat windows MUST consume canonical chat replay from `/chat` and `/chat/history`, not directly from FCMP `/events`.

#### Scenario: Refresh preserves user replies

- **GIVEN** a run has already recorded user replies and assistant replies
- **WHEN** the client reloads the page and requests `/chat/history`
- **THEN** the returned chat timeline contains the same user and assistant bubbles in the same order as the live chat stream

#### Scenario: Auth submit ordering is stable

- **GIVEN** a user submits auth input during waiting-auth
- **WHEN** the backend publishes canonical chat replay
- **THEN** the user auth-submission bubble appears before the subsequent system resume notice
