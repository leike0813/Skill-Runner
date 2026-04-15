## ADDED Requirements

### Requirement: Interactive Attempts Target the Union Contract

Interactive attempts MUST converge against the interactive union schema for both non-final
and final turns.

#### Scenario: Pending branch becomes the formal waiting source
- **WHEN** an interactive attempt converges to the pending branch of the union schema
- **THEN** runtime MUST project it into the canonical `PendingInteraction` shape
- **AND** the run MUST transition into `waiting_user`

#### Scenario: Legacy ask-user markup is not the formal waiting source
- **WHEN** interactive output contains legacy `<ASK_USER_YAML>` or similar deprecated markup
- **THEN** runtime MUST treat that output as an invalid legacy sample for convergence purposes
- **AND** it MUST NOT directly establish `waiting_user` from that markup alone
