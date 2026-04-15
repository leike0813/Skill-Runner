## ADDED Requirements

### Requirement: API Diagnostics Preserve Conservative Phase-5 Semantics

The public API MUST continue to expose the established compatibility signals
while keeping the explicit branch contract primary.

#### Scenario: soft completion remains externally visible as a compatibility completion
- **WHEN** an interactive attempt succeeds through soft completion
- **THEN** API diagnostics and warnings MUST continue to include
  `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`

#### Scenario: waiting fallback remains externally stable
- **WHEN** an interactive attempt falls through to compatibility waiting
- **THEN** clients MUST continue to observe the existing `PendingInteraction`
  shape
- **AND** that payload MAY remain generic/default when no valid pending branch
  resolved
