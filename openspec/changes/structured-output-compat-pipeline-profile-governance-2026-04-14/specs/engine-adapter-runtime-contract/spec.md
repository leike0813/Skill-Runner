## ADDED Requirements

### Requirement: Adapter structured-output dispatch MUST route through the shared runtime pipeline

Adapter command construction and parsed payload handling MUST delegate structured-output transport decisions to the shared runtime pipeline.

#### Scenario: command builder asks pipeline for effective schema artifact
- **WHEN** an adapter constructs a non-passthrough start or resume command
- **THEN** it MUST resolve structured-output CLI arguments from the shared runtime pipeline
- **AND** engine-local command builders MUST NOT independently decide between canonical and compatibility schema artifacts

#### Scenario: parsed payload is canonicalized in shared adapter runtime
- **WHEN** an adapter parser extracts a structured final payload
- **THEN** the shared adapter runtime MUST apply the configured payload canonicalizer before returning the final turn result
- **AND** downstream orchestration MUST receive the canonical payload shape rather than any engine transport shim
