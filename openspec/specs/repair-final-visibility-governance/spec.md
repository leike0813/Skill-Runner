# repair-final-visibility-governance Specification

## Purpose
TBD - created by archiving change repair-final-chat-visibility-governance-2026-04-16. Update Purpose after archive.
## Requirements
### Requirement: Repair final visibility is winner-only

When an emitted assistant final enters a repair chain, the system MUST mark that final as superseded and remove it from the primary chat surface.

#### Scenario: Invalid final enters repair

- **WHEN** an attempt emits `assistant.message.final`
- **AND** output convergence decides the payload must enter repair
- **THEN** the system emits `assistant.message.superseded`
- **AND** the superseded final no longer remains primary-visible in chat

### Requirement: Repair finals share a stable family identity

Repair reruns for the same invalid final MUST share a common `message_family_id`.

#### Scenario: Repair rerun final emission

- **GIVEN** a repair family has already started
- **WHEN** a rerun emits another final message
- **THEN** that final carries the same `message_family_id` as the superseded predecessor

### Requirement: Chat consumers honor supersede mutations

Chat replay/read-model consumers MUST hide superseded finals from the primary chat surface while preserving them as revision history.

#### Scenario: Winner-only rendering

- **GIVEN** a repair family with two emitted finals where the first has been superseded
- **WHEN** chat history is rendered
- **THEN** only the latest non-superseded winner is directly visible
- **AND** the superseded final remains available only as folded revision history

