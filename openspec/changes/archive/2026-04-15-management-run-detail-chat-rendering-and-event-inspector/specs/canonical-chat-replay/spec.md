## ADDED Requirements

### Requirement: Chat replay inspection MUST stay anchored to chat-replay envelopes
Frontend chat inspection features MUST inspect the `chat-replay` event envelopes already derived by the backend instead of reconstructing alternate event views.

#### Scenario: frontend opens a chat event inspector
- **WHEN** a frontend offers raw-event inspection for a chat bubble
- **THEN** the inspected payload MUST be the original `chat-replay` event envelope consumed by that view
- **AND** the frontend MUST NOT fetch or synthesize a different event source just to populate the inspector
