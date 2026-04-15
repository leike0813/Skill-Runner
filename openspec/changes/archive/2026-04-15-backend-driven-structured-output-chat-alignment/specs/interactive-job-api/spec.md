## ADDED Requirements

### Requirement: Pending interaction cards MUST use `ui_hints` as the primary display source
Interactive pending payloads MUST continue exposing compatibility fields such as `prompt`, but frontend prompt cards MUST be able to use `ui_hints.prompt`, `ui_hints.hint`, `ui_hints.options`, and `ui_hints.files` as their primary display surface.

#### Scenario: valid pending branch
- **WHEN** a run is waiting on a valid pending branch
- **THEN** chat MUST show the pending `message`
- **AND** the pending card MUST use `ui_hints.prompt` as its main card text
- **AND** the pending card MUST NOT repeat the chat `message`

#### Scenario: missing `ui_hints.prompt`
- **WHEN** a pending payload lacks `ui_hints.prompt`
- **THEN** the pending card MUST fall back to the stable default open-text prompt
- **AND** the card MUST NOT copy the chat `message` into the prompt-card body
