## MODIFIED Requirements

### Requirement: 系统 MUST 统一 Agent 提问载荷结构
The target pending payload MUST be represented by the pending branch of the interactive union contract.

#### Scenario: pending payload uses message plus ui_hints
- **WHEN** the system creates a target interactive prompt payload
- **THEN** the source contract MUST be a JSON object with `__SKILL_DONE__ = false`
- **AND** it MUST contain non-empty `message`
- **AND** it MUST contain object `ui_hints`

#### Scenario: kind remains compatibility metadata
- **WHEN** frontend classification needs `kind`
- **THEN** `kind` MAY remain compatibility metadata inside `ui_hints` or projected pending payloads
- **AND** it MUST NOT be a backend control-plane prerequisite

### Requirement: interactive 决策策略 MUST 定义完成证据优先级
The target policy MUST prioritize explicit final/pending branches over legacy soft-completion evidence.

#### Scenario: explicit final branch wins completion
- **WHEN** a turn emits a compliant final JSON object
- **THEN** the system MUST converge on completion

#### Scenario: explicit pending branch wins waiting
- **WHEN** a turn emits a compliant pending JSON object
- **THEN** the system MUST converge on waiting for user input

#### Scenario: legacy soft completion is not the target decision rule
- **WHEN** rollout notes mention soft completion
- **THEN** they MUST be labeled legacy/deprecated context
- **AND** they MUST NOT be described as the target decision policy

### Requirement: ask_user 证据 MUST 退役为 legacy 兼容语义
`<ASK_USER_YAML>` MUST be described as deprecated compatibility semantics rather than as a formal protocol.

#### Scenario: legacy wrapper is not the formal contract
- **WHEN** `<ASK_USER_YAML>` is referenced in migration or compatibility notes
- **THEN** it MUST be explicitly labeled deprecated
- **AND** the formal target contract MUST remain the pending JSON branch
