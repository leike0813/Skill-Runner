## MODIFIED Requirements

### Requirement: 系统 MUST 统一 Agent 提问载荷结构
The canonical interactive prompt payload MUST be represented by the pending branch of the union output contract.

#### Scenario: pending branch carries user-facing prompt data
- **WHEN** interaction is created from a compliant agent turn
- **THEN** the source payload MUST be a JSON object with `__SKILL_DONE__ = false`
- **AND** it MUST contain non-empty `message`
- **AND** it MUST contain object `ui_hints`

#### Scenario: kind remains compatibility metadata
- **WHEN** frontend-specific prompt classification is needed
- **THEN** `kind` MAY continue to exist as compatibility metadata inside `ui_hints` or projected pending payloads
- **AND** it MUST NOT become a prerequisite for the pending branch itself

### Requirement: interactive 决策策略 MUST 定义完成证据优先级
The decision policy MUST prioritize explicit union-contract branches over legacy evidence and over fallback repair outcomes.

#### Scenario: explicit final branch wins completion
- **WHEN** a turn emits a compliant final JSON object
- **AND** `__SKILL_DONE__ = true`
- **AND** business fields satisfy output schema
- **THEN** the system MUST converge on completion

#### Scenario: explicit pending branch wins waiting
- **WHEN** a turn emits a compliant pending JSON object
- **AND** `__SKILL_DONE__ = false`
- **AND** `message` and `ui_hints` are valid
- **THEN** the system MUST converge on waiting for user input

#### Scenario: repair is bounded and attempt-local
- **WHEN** a turn fails schema validation
- **THEN** the system MUST run bounded schema repair retries inside the same attempt
- **AND** exceeding the repair retry limit MUST return control to the existing lifecycle decision path

### Requirement: ask_user 证据 MUST 退役为 legacy 兼容语义
`<ASK_USER_YAML>` and equivalent wrapper semantics MUST be treated as deprecated compatibility signals rather than as the primary control-plane protocol.

#### Scenario: legacy wrapper does not define the target contract
- **WHEN** assistant output contains `<ASK_USER_YAML>`
- **THEN** that wrapper MUST be considered deprecated legacy behavior
- **AND** the target compliant protocol MUST instead be the pending JSON branch
