## MODIFIED Requirements

### Requirement: interactive 终态门禁 MUST 先判显式输出分支再决定生命周期
interactive 模式 MUST use an explicit union output contract. Lifecycle gating MUST distinguish final and pending JSON branches before any fallback decision path.

#### Scenario: pending branch enters waiting_user
- **WHEN** 当前 attempt 产出合法的 pending JSON 分支
- **AND** the payload has `__SKILL_DONE__ = false`
- **AND** the payload contains non-empty `message`
- **AND** the payload contains object `ui_hints`
- **THEN** run MUST enter `waiting_user`

#### Scenario: final branch enters completion path
- **WHEN** 当前 attempt 产出合法的 final JSON 分支
- **AND** the payload has `__SKILL_DONE__ = true`
- **AND** business fields satisfy output schema
- **THEN** run MUST enter the completion path

#### Scenario: repair exhaustion falls back to existing lifecycle
- **WHEN** 当前 attempt exhausts schema repair retries
- **THEN** the system MUST exit the repair loop
- **AND** it MUST fall back to the existing lifecycle decision path for that turn
- **AND** repair exhaustion itself MUST NOT directly force `waiting_user`

### Requirement: auto 与 interactive MUST 使用显式 done-marker 最终对象
The target JSON-only contract MUST require explicit final objects in both modes even though implementation rollout may occur later.

#### Scenario: auto final object is explicit
- **WHEN** run 处于 `auto` 模式
- **AND** the task is complete
- **THEN** the target final payload MUST include `__SKILL_DONE__ = true`

#### Scenario: interactive final object is explicit
- **WHEN** run 处于 `interactive` 模式
- **AND** the task is complete
- **THEN** the target final payload MUST include `__SKILL_DONE__ = true`

### Requirement: interactive waiting semantics MUST align to pending JSON branch
The future canonical source for `waiting_user` MUST be the compliant pending JSON branch rather than `<ASK_USER_YAML>` or other free-form wrapper semantics.

#### Scenario: legacy ask-user evidence is deprecated
- **WHEN** a turn uses `<ASK_USER_YAML>` instead of the pending JSON branch
- **THEN** that output MUST be classified as legacy deprecated semantics
- **AND** it MUST NOT remain the normative contract for compliant implementations
