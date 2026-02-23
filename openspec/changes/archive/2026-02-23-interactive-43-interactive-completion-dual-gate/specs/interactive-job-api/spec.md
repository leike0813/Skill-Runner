## MODIFIED Requirements

### Requirement: 系统 MUST 提供待决交互查询接口
The pending payload minimum viability MUST be guaranteed by backend-owned generation and MUST NOT depend on agent-structured ask_user output.

#### Scenario: waiting_user 下总能返回可回复 pending
- **GIVEN** run 状态为 `waiting_user`
- **WHEN** 客户端调用 pending 接口
- **THEN** 返回可用于 reply 的 `interaction_id` 与 `prompt`
- **AND** 其来源可以是后端基线生成，而非 ask_user 原样透传

### Requirement: 系统 MUST 提供交互回复接口
The reply protocol MUST remain `interaction_id + response` driven and MUST NOT introduce semantic coupling to `kind`.

#### Scenario: kind 仅兼容展示
- **WHEN** pending 载荷包含 `kind`
- **THEN** 客户端可用于展示
- **AND** 后端不依赖该字段做语义理解或强约束验证

## ADDED Requirements

### Requirement: waiting_user 进入条件 MUST 独立于 ask_user 结构体
系统 MUST 允许在缺少或损坏 ask_user 结构时，仍通过 interactive gate 进入等待态。

#### Scenario: 缺失 ask_user 仍可等待用户
- **GIVEN** run 处于 `interactive` 模式
- **WHEN** 当前回合未检测到 done marker
- **THEN** run 可进入 `waiting_user`
- **AND** pending/reply 闭环保持可用

### Requirement: API 状态与诊断 MUST 反映双轨完成与回合上限策略
系统 MUST 向客户端公开稳定、可消费的完成告警与失败原因。

#### Scenario: 软条件完成返回稳定 warning
- **WHEN** interactive 回合未检测到 done marker 但输出通过 schema 校验并完成
- **THEN** API 响应中的诊断/告警包含 `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`

#### Scenario: 超轮次失败返回稳定错误码
- **WHEN** interactive 回合达到 `max_attempt` 且本回合无完成证据
- **THEN** API 返回 `failed`
- **AND** 失败原因包含 `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`
