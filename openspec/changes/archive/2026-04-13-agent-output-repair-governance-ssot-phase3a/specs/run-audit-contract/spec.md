## ADDED Requirements

### Requirement: run audit MUST reserve a repair-round history surface
The target audit contract MUST include a dedicated attempt-scoped repair history stream.

#### Scenario: repair-round audit file is canonical target history
- **WHEN** phase 3B emits output-convergence round history
- **THEN** the canonical file MUST be `.audit/output_repair.<attempt>.jsonl`
- **AND** each record MUST be history-only and append-only
- **AND** current runtime MAY leave this file absent until the implementation phase begins

### Requirement: repair audit records MUST follow the attempt/internal-round model
The target repair audit stream MUST reflect the same dual-layer governance model as the machine contract.

#### Scenario: repair round audit includes executor and fallback context
- **WHEN** a repair record is written
- **THEN** it MUST identify the outer `attempt_number`
- **AND** it MUST identify the `internal_round_index`
- **AND** it MUST capture `repair_stage`, `candidate_source`, and any legacy fallback target reached after repair stops
