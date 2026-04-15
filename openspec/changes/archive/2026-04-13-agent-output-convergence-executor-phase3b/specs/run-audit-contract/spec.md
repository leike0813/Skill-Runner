## ADDED Requirements

### Requirement: Repair Round Audit History

Each attempt MUST expose a canonical repair-round history file.

#### Scenario: Repair audit tracks parse and schema outcomes
- **WHEN** an attempt enters the output convergence loop
- **THEN** runtime MUST append records to `.audit/output_repair.<attempt>.jsonl`
- **AND** each round record MUST indicate whether deterministic parse repair was applied
- **AND** each round record MUST indicate whether deterministic parse repair succeeded
- **AND** each round record MUST indicate whether schema validation succeeded
- **AND** exhausted or skipped records MUST identify the legacy fallback target
