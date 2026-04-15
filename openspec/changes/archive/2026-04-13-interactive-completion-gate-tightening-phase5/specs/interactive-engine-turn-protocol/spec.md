## ADDED Requirements

### Requirement: Interactive Turn Protocol Distinguishes Formal Branches From Compatibility Paths

Interactive turn processing MUST keep the formal contract and compatibility
fallbacks distinct.

#### Scenario: pending branch remains the formal waiting source
- **WHEN** an interactive turn produces a valid pending JSON branch
- **THEN** runtime MUST project that branch into canonical `PendingInteraction`
- **AND** this path MUST be preferred over compatibility waiting fallback

#### Scenario: missing explicit branch may still soft-complete
- **WHEN** an interactive turn does not resolve a valid final or pending branch
- **AND** business output remains schema-valid
- **THEN** runtime MAY still classify the turn as soft completion
- **AND** that classification MUST remain a compatibility path

#### Scenario: compatibility waiting fallback stays generic
- **WHEN** an interactive turn reaches waiting fallback instead of a valid
  pending branch
- **THEN** runtime MUST use the default pending payload
- **AND** it MUST NOT restore deprecated ask-user enrichment
