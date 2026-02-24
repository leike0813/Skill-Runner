## ADDED Requirements

### Requirement: 系统 MUST 定义 FCMP 最小完备事件集
系统 MUST 至少提供以下事件类型：`conversation.state.changed`、`interaction.reply.accepted`、`interaction.auto_decide.timeout`，用于覆盖状态迁移与交互恢复语义。

#### Scenario: 事件集完备
- **WHEN** run 经历 waiting/reply/timeout/resume 生命周期
- **THEN** 客户端可仅通过 FCMP 事件恢复完整语义

### Requirement: `conversation.state.changed` payload MUST 稳定
系统 MUST 提供稳定字段：`from`、`to`、`trigger`、`updated_at`、`pending_interaction_id?`。

#### Scenario: waiting_user 进入
- **WHEN** run 进入 `waiting_user`
- **THEN** payload `to=waiting_user`
- **AND** `trigger=turn.needs_input`

### Requirement: 交互恢复事件 payload MUST 稳定
系统 MUST 为 `interaction.reply.accepted` 与 `interaction.auto_decide.timeout` 提供稳定字段。

#### Scenario: 用户回复被接受
- **WHEN** reply 提交并被接受
- **THEN** 事件包含 `interaction_id` 与 `resolution_mode=user_reply`

#### Scenario: strict=false 超时自动决策
- **WHEN** 超时触发自动决策
- **THEN** 事件包含 `interaction_id`、`resolution_mode=auto_decide_timeout`、`timeout_sec`、`policy`
