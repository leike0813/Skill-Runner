## ADDED Requirements

### Requirement: Orchestration publishes canonical chat replay side effects

When orchestration accepts interaction replies, auth submissions, or emits user-visible system notices, it MUST publish canonical chat replay rows in addition to any FCMP/runtime protocol events.

#### Scenario: Interaction reply emits user chat replay row

- **GIVEN** an interactive reply is accepted
- **WHEN** orchestration persists the reply
- **THEN** a canonical `user` chat replay row is published for that reply

#### Scenario: Auth completion emits system chat replay row

- **GIVEN** auth completes successfully
- **WHEN** orchestration issues the resume path
- **THEN** a canonical `system` chat replay row is published describing the resume notice
