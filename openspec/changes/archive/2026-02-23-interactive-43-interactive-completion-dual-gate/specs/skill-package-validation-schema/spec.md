## ADDED Requirements

### Requirement: runner manifest MUST 支持 interactive 最大回合声明
`assets/runner.json` 合同 MUST 支持可选字段 `max_attempt`，用于约束 interactive 最大交互回合数。

#### Scenario: max_attempt 合法取值通过校验
- **WHEN** `runner.json.max_attempt` 为正整数（如 `1`、`10`）
- **THEN** skill 包通过 manifest 合同校验

#### Scenario: max_attempt 非法取值拒绝
- **WHEN** `runner.json.max_attempt` 为 `0`、负数或非整数
- **THEN** skill 包被拒绝为合同无效

### Requirement: max_attempt 语义 MUST 限定于 interactive 模式
`max_attempt` MUST only affect interactive execution lifecycle.

#### Scenario: auto 模式忽略 max_attempt
- **WHEN** run 以 `auto` 模式执行且 manifest 声明 `max_attempt`
- **THEN** 系统不以该字段触发自动失败
