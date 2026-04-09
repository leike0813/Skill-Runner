## ADDED Requirements

### Requirement: `interaction/reply` auth submission MUST support custom_provider
The `interaction/reply` payload in `mode=auth` MUST support `submission.kind=custom_provider` for provider-config waiting_auth sessions.

#### Scenario: client submits provider-config auth payload
- **GIVEN** a Claude run is in `waiting_auth`
- **AND** the current auth challenge is a provider-config challenge
- **WHEN** the client submits `POST /interaction/reply` with `mode=auth`
- **THEN** `submission.kind` MUST accept `custom_provider`
- **AND** the backend MUST treat it as the canonical provider-config submission kind
