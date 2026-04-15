## ADDED Requirements

### Requirement: pending payload minimum viability MUST align with target pending JSON projection
The target `PendingInteraction` source MUST be a legal pending JSON branch projected into the existing external API shape.

#### Scenario: pending projection keeps API shape stable
- **WHEN** the backend exposes a pending interaction through the public API
- **THEN** the external `PendingInteraction` shape MAY remain unchanged
- **AND** the target source MUST be the pending JSON branch projected into that shape

#### Scenario: legacy backend-generated or heuristic pending data is rollout-only
- **WHEN** documentation references heuristic or legacy pending generation
- **THEN** it MUST be labeled rollout/deprecated/current-implementation-only
- **AND** it MUST NOT be presented as the target source

### Requirement: interactive completion semantics MUST require explicit final branch
The target interactive API semantics MUST not define soft completion as the normative completion path.

#### Scenario: final result requires explicit done marker
- **WHEN** an interactive run is complete under the target contract
- **THEN** the final output MUST explicitly include `__SKILL_DONE__ = true`

#### Scenario: soft completion is legacy context only
- **WHEN** API documentation mentions completion without explicit done marker
- **THEN** it MUST be marked as legacy rollout context only
