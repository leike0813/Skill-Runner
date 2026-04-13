## ADDED Requirements

### Requirement: Attempt-Level Output Convergence Loop

Each runtime attempt MUST be governed by one orchestrator-owned output convergence loop.

#### Scenario: Deterministic parse repair runs inside each loop iteration
- **WHEN** an attempt produces raw assistant output
- **THEN** the orchestrator MUST first apply deterministic parse normalization for that loop iteration
- **AND** only the normalized candidate is validated against the attempt target schema
- **AND** downstream fallback logic MUST NOT repeat deterministic parse repair after loop exhaustion

#### Scenario: Repair reruns are handle-gated
- **WHEN** the attempt output still does not satisfy the target schema after deterministic parse normalization
- **THEN** the orchestrator MAY issue a repair rerun only if a persisted session handle already exists
- **AND** the rerun MUST stay within the same `attempt_number`
- **AND** the rerun MUST increment `internal_round_index`

#### Scenario: No session handle skips repair
- **WHEN** a repair rerun would otherwise be required but no session handle exists
- **THEN** the orchestrator MUST emit `diagnostic.output_repair.skipped`
- **AND** the skip reason MUST identify the missing session handle
- **AND** runtime MUST continue via the legacy fallback chain without a repair rerun
