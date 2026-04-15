## MODIFIED Requirements

### Requirement: Management run detail MUST render backend-projected chat text
The management run-detail page MUST treat canonical chat as a backend-derived display surface and MUST NOT perform its own structured-output dispatch.

#### Scenario: final structured output appears in management chat
- **WHEN** `/chat` supplies assistant final text rendered as markdown
- **THEN** the management run-detail page MUST render that markdown in chat
- **AND** it MUST NOT re-parse raw structured JSON to decide how to display the message

#### Scenario: pending structured output appears in management chat
- **WHEN** `/chat` supplies pending display text
- **THEN** the management run-detail page MUST render the projected text directly
- **AND** it MUST NOT add a second final summary card for the same content
