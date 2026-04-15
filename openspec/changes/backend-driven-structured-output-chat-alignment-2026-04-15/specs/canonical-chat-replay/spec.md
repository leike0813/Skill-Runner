## MODIFIED Requirements

### Requirement: Canonical chat replay MUST consume backend-projected assistant final display text
Chat replay MUST treat `assistant.message.final` as an already-projected display event and MUST prefer `data.display_text` over raw `data.text` when present.

#### Scenario: assistant final contains projected display text
- **WHEN** an `assistant.message.final` FCMP event includes `data.display_text`
- **THEN** canonical chat replay MUST derive the assistant bubble from `data.display_text`
- **AND** the raw compatibility field `data.text` MUST remain available without becoming the primary chat text

#### Scenario: assistant final has no projected display text
- **WHEN** an `assistant.message.final` FCMP event omits `data.display_text`
- **THEN** canonical chat replay MAY fall back to `data.text`

## ADDED Requirements

### Requirement: Chat replay MUST stay free of local structured-output dispatch
Frontend-facing chat replay MUST remain a derived view and MUST NOT require clients to parse `__SKILL_DONE__`, `message`, or `ui_hints` out of assistant final text.

#### Scenario: structured output reaches chat
- **WHEN** a frontend consumes `/chat` or `/chat/history`
- **THEN** the chat payload MUST already reflect the backend-projected display text
- **AND** frontend chat consumers MUST be able to render the message without local structured-output branching
