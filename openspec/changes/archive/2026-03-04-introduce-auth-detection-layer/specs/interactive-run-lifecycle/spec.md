## MODIFIED Requirements

### Requirement: 系统 MUST 支持可暂停交互生命周期
系统 MUST 在 interactive 回合无完成证据时进入 `waiting_user`，且不依赖 ask_user 结构完整性；但高置信度 auth detection 必须优先于 generic `waiting_user` 推断。

#### Scenario: 高置信度鉴权证据阻止 waiting_user
- **GIVEN** 输出包含高置信度 auth-required 证据
- **WHEN** run_job 归一化结果
- **THEN** 系统不得进入 `waiting_user`
- **AND** generic pending interaction 推断必须被跳过

#### Scenario: medium 问题样本保持保守
- **GIVEN** 输出只命中 medium 级问题样本
- **WHEN** run_job 归一化结果
- **THEN** 系统可以继续现有等待态逻辑
- **AND** 必须保留 auth detection 审计字段
