## MODIFIED Requirements

### Requirement: 系统 MUST 通过统一 output convergence executor 管理修复链
The target repair model MUST be governed by a single orchestrator-side output convergence executor.

#### Scenario: deterministic parse repair is pre-processing, not a separate owner
- **WHEN** parser or adapter yields a repaired JSON candidate
- **THEN** that repaired candidate MUST re-enter the orchestrator-owned output convergence pipeline
- **AND** parser/adapter repair MUST NOT become a separate completion or waiting classifier

#### Scenario: result-file fallback remains inside the same governance model
- **WHEN** the primary structured-output path fails to converge
- **THEN** result-file fallback MUST be described as a legacy downstream stage within the same output convergence model
- **AND** it MUST NOT be described as an unrelated recovery subsystem

### Requirement: 系统 MUST 使用 `attempt + internal_round` 双层 repair 模型
The target repair model MUST distinguish outer attempts from inner convergence rounds.

#### Scenario: repair rounds stay inside the current attempt
- **WHEN** a turn enters repair
- **THEN** each convergence retry MUST be represented as an `internal_round`
- **AND** the retries MUST stay inside the current `attempt_number`

#### Scenario: repair round budget is bounded
- **WHEN** repair executes
- **THEN** the default `internal_round` retry budget MUST be 3
- **AND** exhaustion MUST return control to legacy lifecycle fallback instead of creating a new attempt

### Requirement: Repair MUST remain schema-first while preserving legacy fallback ordering
Repair only converges when a compliant branch exists; otherwise the target model returns control to the legacy fallback chain in a fixed order.

#### Scenario: compliant final branch converges
- **WHEN** output convergence yields a compliant final JSON object
- **THEN** the turn MAY continue on the completion path

#### Scenario: repair exhaustion returns to legacy chain
- **WHEN** the `internal_round` budget is exhausted without a compliant branch
- **THEN** the output convergence executor MUST stop repair
- **AND** it MUST return control to legacy lifecycle fallback first
- **AND** later legacy stages MAY still include result-file fallback or interactive waiting heuristics
