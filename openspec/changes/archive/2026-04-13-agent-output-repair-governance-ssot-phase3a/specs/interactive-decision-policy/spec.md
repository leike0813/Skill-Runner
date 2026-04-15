## ADDED Requirements

### Requirement: repair decision ownership MUST belong to the orchestrator convergence executor
Interactive repair decisions MUST be owned by a single orchestrator-side convergence executor.

#### Scenario: parser repair cannot independently classify the turn
- **WHEN** deterministic generic repair produces a usable candidate
- **THEN** the candidate MUST be evaluated by the orchestrator-owned convergence executor
- **AND** parser-level repair MUST NOT independently classify the turn as complete or waiting

#### Scenario: waiting fallback remains outside repair ownership in current runtime
- **WHEN** current runtime behavior derives `waiting_user` from legacy ask-user or invalid-structured-output heuristics
- **THEN** those paths MUST be documented as lifecycle fallback semantics
- **AND** they MUST remain outside target repair ownership until a later implementation phase switches the source
