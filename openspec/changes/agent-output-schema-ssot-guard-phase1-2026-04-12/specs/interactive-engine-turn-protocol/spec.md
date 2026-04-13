## MODIFIED Requirements

### Requirement: 引擎适配层 MUST 输出统一回合协议
The system MUST treat agent turn output as a JSON-object protocol target, and legacy ask-user side channels MUST NOT remain the primary control-plane contract.

#### Scenario: pending turn uses explicit JSON branch
- **WHEN** an `interactive` turn needs user input
- **THEN** the target protocol for that turn MUST be a JSON object with `__SKILL_DONE__ = false`
- **AND** the object MUST include a non-empty `message`
- **AND** the object MUST include `ui_hints` as an object

#### Scenario: legacy ask-user wrapper is non-primary
- **WHEN** an agent emits `<ASK_USER_YAML>` or any equivalent legacy wrapper
- **THEN** the system MUST treat it as deprecated legacy compatibility semantics
- **AND** it MUST NOT remain the target output contract for future compliant implementations

### Requirement: 运行时补丁 MUST 与执行模式一致
Runtime patching MUST remain mode-aware; it MUST instruct agents to return JSON-only output objects, and `interactive` patching MUST describe final vs pending branches within one output contract.

#### Scenario: interactive patch describes union contract
- **WHEN** run 以 `interactive` 模式执行
- **THEN** the patch MUST describe a single union output contract
- **AND** the final branch MUST require `__SKILL_DONE__ = true`
- **AND** the pending branch MUST require `__SKILL_DONE__ = false`, `message`, and `ui_hints`

#### Scenario: auto patch requires explicit final object
- **WHEN** run 以 `auto` 模式执行
- **THEN** the patch MUST require a JSON object
- **AND** the object MUST explicitly include `__SKILL_DONE__ = true`

### Requirement: 完成态判定 MUST 按 execution_mode 区分
The system MUST converge both execution modes on explicit JSON-object contracts while preserving mode-specific validation targets.

#### Scenario: interactive final turn uses explicit final branch
- **WHEN** run 以 `interactive` 模式执行
- **AND** the turn is complete
- **THEN** the target output MUST be a JSON object with `__SKILL_DONE__ = true`
- **AND** business fields MUST satisfy the skill output schema after stripping `__SKILL_DONE__`

#### Scenario: auto final turn requires explicit final marker
- **WHEN** run 以 `auto` 模式执行
- **AND** the turn is complete
- **THEN** the target output MUST be a JSON object with `__SKILL_DONE__ = true`
- **AND** business fields MUST satisfy the skill output schema after stripping `__SKILL_DONE__`

#### Scenario: pending branch is not a final payload
- **WHEN** run 以 `interactive` 模式执行
- **AND** a turn emits `__SKILL_DONE__ = false`
- **THEN** that payload MUST be interpreted as pending rather than final
- **AND** it MUST NOT be validated against the final business output branch

### Requirement: repair MUST NOT decide completion
Repair MUST act as same-attempt schema convergence only; it MUST NOT invent waiting-state control flow or upgrade deprecated legacy ask-user payloads into compliant final outputs.

#### Scenario: repair stays inside one attempt
- **WHEN** a turn fails schema validation and enters repair
- **THEN** each repair retry MUST remain inside the current attempt
- **AND** repair MUST NOT increment `attempt_number`

#### Scenario: repair cannot transform legacy ask-user into primary protocol
- **WHEN** a turn only provides legacy ask-user wrapper evidence
- **THEN** repair MUST NOT treat that wrapper as the target compliant protocol
- **AND** future compliant behavior MUST instead produce the pending JSON branch
