## MODIFIED Requirements

### Requirement: 系统 MUST 提供自动决策策略提示字段
系统 MUST 在 strict=false 超时路径消费 `default_decision_policy` 并生成自动决策回复。

#### Scenario: strict=false 超时自动决策
- **GIVEN** `interactive_require_user_reply=false`
- **WHEN** waiting 超时触发自动决策
- **THEN** 系统基于 `default_decision_policy` 生成 auto reply
- **AND** 记录 `resolution_mode=auto_decide_timeout`

## ADDED Requirements

### Requirement: strict=true MUST 保持人工门禁
系统 MUST 在 strict=true 下仅等待用户回复或取消。

#### Scenario: strict=true 不自动推进
- **GIVEN** `interactive_require_user_reply=true`
- **WHEN** waiting 超时
- **THEN** 系统不自动提交回复
