# e2e-waiting-user-choice-hints-freeform-reply Specification

## Purpose
TBD - created by archiving change e2e-waiting-user-choice-hints-freeform-reply-2026-04-17. Update Purpose after archive.
## Requirements
### Requirement: E2E waiting-user prompts keep freeform reply available

The e2e run observe page MUST keep the freeform reply composer available during `waiting_user`, even when `ui_hints.kind` is not `open_text`.

#### Scenario: Non-open-text waiting-user prompt shows both choices and composer
- **WHEN** the e2e frontend renders a `waiting_user` prompt whose `ui_hints.kind` is not `open_text`
- **THEN** the prompt-card choices remain visible
- **AND** the reply composer remains visible and enabled
- **AND** the reply composer uses a compact single-line visual style

### Requirement: Non-open-text waiting-user prompts use a dedicated placeholder

The e2e frontend MUST use a dedicated localized placeholder for non-`open_text` freeform reply.

#### Scenario: Compact composer placeholder
- **WHEN** the e2e frontend renders a non-`open_text` waiting-user prompt
- **THEN** the composer placeholder uses the dedicated “or enter a different request...” locale key
- **AND** it does not reuse `ui_hints.hint` as the freeform placeholder

