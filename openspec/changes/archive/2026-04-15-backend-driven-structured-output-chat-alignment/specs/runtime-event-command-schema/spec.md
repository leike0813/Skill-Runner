## ADDED Requirements

### Requirement: `assistant.message.final` MUST support additive display projection fields
The runtime event contract MUST allow additive display-projection fields on `assistant.message.final.data` without changing the event type or removing `text`.

#### Scenario: projected pending display
- **WHEN** the backend recognizes a pending structured-output branch
- **THEN** `assistant.message.final.data` MUST be allowed to contain `display_text`, `display_format`, and `display_origin`
- **AND** `display_text` MUST carry the pending `message`

#### Scenario: projected final display
- **WHEN** the backend recognizes a final structured-output branch
- **THEN** `assistant.message.final.data.display_text` MUST carry the rendered final payload text
- **AND** `assistant.message.final.data.text` MUST remain a valid compatibility field
