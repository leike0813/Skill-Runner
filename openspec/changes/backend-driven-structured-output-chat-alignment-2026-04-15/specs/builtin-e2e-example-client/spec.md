## MODIFIED Requirements

### Requirement: E2E observe chat MUST use backend-projected display text only
The built-in E2E observe client MUST keep its conversation panel on `/chat` and MUST NOT locally dispatch final/pending structured JSON for display.

#### Scenario: pending branch arrives
- **WHEN** the run is waiting on a pending branch
- **THEN** the conversation panel MUST show the backend-projected pending `message`
- **AND** the prompt card MUST use `ui_hints.prompt` / `ui_hints.hint` / `ui_hints.options` / `ui_hints.files`
- **AND** the prompt card MUST NOT duplicate the pending `message`

#### Scenario: final branch arrives
- **WHEN** the run completes with a final structured-output branch
- **THEN** the conversation panel MUST render the backend-projected final display text
- **AND** the client MUST NOT show a separate final summary card for the same structured output
