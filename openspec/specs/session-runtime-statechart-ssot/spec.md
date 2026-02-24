# session-runtime-statechart-ssot Specification

## Purpose
定义 session 运行时状态机 SSOT，约束实现、协议和测试一致演进。

## Requirements
### Requirement: 系统 MUST 维护统一 canonical 状态机
系统 MUST 以 `queued/running/waiting_user/succeeded/failed/canceled` 作为唯一 canonical 状态集合。

#### Scenario: canonical 生命周期
- **WHEN** run 正常执行
- **THEN** 生命周期遵循 `queued -> running -> waiting_user -> queued -> running -> terminal`

### Requirement: 系统 MUST 以状态机事件驱动关键分支
系统 MUST 使用显式事件集合驱动状态转换，而不是散落条件分支。

#### Scenario: waiting_user 回复事件
- **GIVEN** run 处于 `waiting_user`
- **WHEN** 接收 `interaction.reply.accepted`
- **THEN** run 转为 `queued`

#### Scenario: strict=false 超时自动决策事件
- **GIVEN** run 处于 `waiting_user`
- **AND** `interactive_require_user_reply=false`
- **WHEN** 超时触发自动决策
- **THEN** 触发 `interaction.auto_decide.timeout`
- **AND** run 转为 `queued`

### Requirement: 重启恢复 MUST 使用统一恢复事件
系统 MUST 通过统一恢复事件收敛 `waiting_user` 的启动恢复分流。

#### Scenario: 恢复保留 waiting
- **GIVEN** run 处于 `waiting_user`
- **AND** pending + session handle 有效
- **WHEN** orchestrator 启动恢复
- **THEN** 触发 `restart.preserve_waiting`
- **AND** run 维持 `waiting_user`

#### Scenario: 恢复失败收敛
- **GIVEN** run 处于 `waiting_user`
- **AND** pending 或 session handle 无效
- **WHEN** orchestrator 启动恢复
- **THEN** 触发 `restart.reconcile_failed`
- **AND** run 转为 `failed`

### Requirement: auto MUST 作为 interactive 子集建模
系统 MUST 将 `auto` 建模为同一状态机下的策略子集，而非独立核心状态机。

#### Scenario: auto 终态映射一致
- **WHEN** run 处于 `auto` 模式
- **THEN** 终态仍仅为 `succeeded|failed|canceled`
- **AND** 协议终态映射与 interactive 一致

### Requirement: canonical 状态事件 MUST 映射到 FCMP 显式事件
系统 MUST 为关键状态转换输出 FCMP `conversation.state.changed`，并为回复/自动决策输出对应 FCMP 事件。

#### Scenario: 用户回复恢复
- **WHEN** 触发 `interaction.reply.accepted`
- **THEN** FCMP 输出 `interaction.reply.accepted`
- **AND** 输出 `conversation.state.changed(from=waiting_user,to=queued,trigger=interaction.reply.accepted)`

#### Scenario: 自动决策恢复
- **WHEN** 触发 `interaction.auto_decide.timeout`
- **THEN** FCMP 输出 `interaction.auto_decide.timeout`
- **AND** 输出 `conversation.state.changed(from=waiting_user,to=queued,trigger=interaction.auto_decide.timeout)`

### Requirement: 状态与回复事件 payload MUST 满足固定字段合同
系统 MUST 对关键状态与交互事件 payload 执行 schema 校验。

#### Scenario: state.changed 字段完整
- **WHEN** 输出 `conversation.state.changed`
- **THEN** payload 包含 `from`、`to`、`trigger`、`updated_at`

#### Scenario: reply.accepted 字段完整
- **WHEN** 输出 `interaction.reply.accepted`
- **THEN** payload 包含 `interaction_id`、`resolution_mode=user_reply`、`accepted_at`

#### Scenario: auto_decide.timeout 字段完整
- **WHEN** 输出 `interaction.auto_decide.timeout`
- **THEN** payload 包含 `interaction_id`、`resolution_mode=auto_decide_timeout`、`policy`

### Requirement: canonical 状态机不变量 MUST 合同化并由模型测试守护
系统 MUST 将 canonical 状态/转移不变量沉淀为机器可读合同，并由模型测试校验实现一致性。

#### Scenario: 合同-实现转移一致
- **WHEN** 执行状态机模型测试
- **THEN** 合同转移集合与实现转移集合双向等价

#### Scenario: 有限序列等价
- **WHEN** 对有限事件序列进行模型回放
- **THEN** 合同模型与实现模型得到相同的状态结果
