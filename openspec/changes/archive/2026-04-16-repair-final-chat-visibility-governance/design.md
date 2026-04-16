# Design

## Core rule

For any repair family:

- an emitted `assistant.message.final` remains visible only until repair starts
- once repair starts for that final, the system emits `assistant.message.superseded`
- the superseded final leaves the primary chat surface
- the repair family ultimately has exactly one visible winner

The winner may be:

- the converged repaired final
- a terminal fallback final/notice
- a non-terminal canonical waiting message

Old superseded finals never reappear as primary-visible content.

## Identity

- `message_id`: unique identity of a concrete final message
- `message_family_id`: stable identity shared by all finals in one repair chain

Default behavior:

- non-repair finals use `message_family_id == message_id`
- repair reruns reuse the original family id

## Event model

### New FCMP event

- `assistant.message.superseded`

Payload:

- `message_id`
- `message_family_id`
- `reason=output_repair_started`
- `repair_round_index`
- `replacement_expected=true`

### Internal orchestration hook

Repair governance emits an orchestrator event that is translated to FCMP `assistant.message.superseded` and to chat replay revision rows.

## Chat replay behavior

Chat replay remains append-only, but now includes a revision mutation row for supersede events.

- `assistant_final` rows represent concrete final messages
- `assistant_revision` rows represent "this previously emitted final is no longer primary-visible"

UI/model behavior consumes append-only rows and materializes winner-only visibility.

## Compatibility

- No change to run state or outcome precedence
- No deletion of raw stdout/stderr or repair audit history
- Existing UIs that do not understand revision rows must not render them as regular assistant bubbles
