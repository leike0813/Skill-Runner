## ADDED Requirements

### Requirement: PendingInteraction Shape Remains Stable During Source Cutover

Phase 4 MUST preserve the external `PendingInteraction` shape while changing its
source priority.

#### Scenario: Pending JSON and fallback share the same external schema
- **WHEN** clients read the pending interaction payload for a `waiting_user` run
- **THEN** they MUST continue to observe the existing external
  `PendingInteraction` shape
- **AND** pending JSON branches may populate rich fields
- **AND** legacy fallback payloads may remain generic within that same shape
