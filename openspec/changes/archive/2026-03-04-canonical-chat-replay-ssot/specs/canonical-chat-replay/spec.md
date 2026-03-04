## ADDED Requirements

### Requirement: Canonical chat replay is the chat SSOT

Canonical chat replay MUST be the only authoritative source for rendering user, assistant, and system chat bubbles.

#### Scenario: Live and history use the same chat source

- **GIVEN** a run is active or recently completed
- **WHEN** the client streams `/chat` or fetches `/chat/history`
- **THEN** both responses reflect the same canonical chat ordering

### Requirement: Frontends must not optimistic-render chat bubbles

Frontends MUST NOT append local chat bubbles for replies or auth submissions before the backend publishes canonical chat replay rows.

#### Scenario: Reply submit waits for backend chat replay

- **GIVEN** a user submits a reply
- **WHEN** the frontend waits for the chat update
- **THEN** the chat bubble only appears after it is received from canonical chat replay
