## MODIFIED Requirements

### Requirement: 系统 MUST 支持可暂停交互生命周期
系统 MUST 在 interactive 回合中区分 `waiting_user` 与 `waiting_auth` 两种可暂停状态；高置信度 auth detection 必须优先于 generic `waiting_user` 推断。

#### Scenario: 高置信度鉴权证据进入 waiting_auth
- **GIVEN** 输出包含高置信度 auth-required 证据
- **AND** run 属于会话型客户端场景
- **WHEN** run_job 归一化结果
- **THEN** 系统必须进入 `waiting_auth`
- **AND** generic pending interaction 推断必须被跳过

#### Scenario: medium 问题样本不误入 waiting_auth
- **GIVEN** 输出只命中 medium 级问题样本
- **WHEN** run_job 归一化结果
- **THEN** 系统不得仅因该结果进入 `waiting_auth`
- **AND** 必须保留 auth detection 审计字段

### Requirement: waiting_user 槽位语义 MUST 统一
系统 MUST 将 `waiting_auth` 视为与 `waiting_user` 同级的暂停态：进入等待态时释放执行槽位，恢复执行前重新申请槽位。

#### Scenario: 进入 waiting_auth 释放槽位
- **GIVEN** run 已持有并发槽位
- **WHEN** run 进入 `waiting_auth`
- **THEN** 系统释放该槽位

#### Scenario: auth 恢复执行前重新申请槽位
- **GIVEN** run 从 `waiting_auth` 恢复执行
- **WHEN** 回到执行路径
- **THEN** 系统在进入 `running` 前重新申请槽位
