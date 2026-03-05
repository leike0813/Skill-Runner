## ADDED Requirements

### Requirement: Run audit contract MUST be independent from request directories

System MUST keep run audit artifacts rooted in run directory and MUST NOT require request directory snapshots for audit completeness.

#### Scenario: request snapshot persisted from DB payload
- **WHEN** run starts from unified request store
- **THEN** run audit snapshot MUST be derivable from DB request payload
- **AND** audit flow MUST NOT depend on `data/requests/{request_id}`

### Requirement: Unified run observability MUST not expose run_source split

Run observability and replay MUST be keyed by request/run identity only, without installed/temp source branching.

#### Scenario: single observability path for run replay
- **WHEN** client reads run events/chat/history
- **THEN** backend MUST serve unified `/v1/jobs/{request_id}` observability paths
- **AND** response semantics MUST be source-agnostic
