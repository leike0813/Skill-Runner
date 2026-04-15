## MODIFIED Requirements

### Requirement: 引擎适配层 MUST 输出统一回合协议
The target interactive turn contract MUST be JSON-only. Legacy ask-user wrappers MAY still exist in current implementation paths, but they MUST be treated as deprecated rollout behavior rather than as the formal protocol.

#### Scenario: pending turn uses pending JSON branch
- **WHEN** an interactive turn needs user input
- **THEN** the target protocol MUST be a JSON object with `__SKILL_DONE__ = false`
- **AND** it MUST include non-empty `message`
- **AND** it MUST include object `ui_hints`

#### Scenario: legacy wrapper is rollout-only
- **WHEN** documentation or migration notes mention `<ASK_USER_YAML>`
- **THEN** that wrapper MUST be labeled legacy / deprecated / current-implementation-only
- **AND** it MUST NOT be presented as the formal target protocol

### Requirement: 运行时补丁 MUST 与执行模式一致
Runtime patching for the target contract MUST describe explicit JSON-only branches rather than YAML-side-channel interaction output.

#### Scenario: interactive patch describes the union contract
- **WHEN** execution mode is `interactive`
- **THEN** the target patch contract MUST describe one union output object
- **AND** the final branch MUST require `__SKILL_DONE__ = true`
- **AND** the pending branch MUST require `__SKILL_DONE__ = false`, `message`, and `ui_hints`

#### Scenario: auto patch requires explicit final object
- **WHEN** execution mode is `auto`
- **THEN** the target patch contract MUST require a JSON object with explicit `__SKILL_DONE__ = true`

### Requirement: 完成态判定 MUST 按 execution_mode 区分
The target contract MUST remove soft-completion semantics from normative completion rules.

#### Scenario: interactive final turn requires explicit final branch
- **WHEN** an interactive turn is complete under the target contract
- **THEN** it MUST emit a JSON object with `__SKILL_DONE__ = true`
- **AND** business fields MUST satisfy the skill output schema

#### Scenario: legacy soft completion is not the target rule
- **WHEN** historical rollout notes mention completion without explicit done marker
- **THEN** they MUST be labeled as legacy rollout context
- **AND** they MUST NOT be presented as the target completion rule
