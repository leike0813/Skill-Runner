## MODIFIED Requirements

### Requirement: 状态事件 payload MUST 满足固定字段合同
系统 MUST 为 `conversation.state.changed` 提供稳定字段并通过 schema 校验。

#### Scenario: 关键字段完整
- **WHEN** 输出 `conversation.state.changed`
- **THEN** payload 至少包含 `from`、`to`、`trigger`、`updated_at`

### Requirement: 回复与自动决策事件 payload MUST 固定
系统 MUST 为 `interaction.reply.accepted` 与 `interaction.auto_decide.timeout` 输出固定字段结构。

#### Scenario: 用户回复恢复
- **WHEN** `waiting_user -> queued` 由用户回复触发
- **THEN** 事件包含 `interaction_id`、`resolution_mode=user_reply`、`accepted_at`

#### Scenario: 自动决策恢复
- **WHEN** `waiting_user -> queued` 由超时自动决策触发
- **THEN** 事件包含 `interaction_id`、`resolution_mode=auto_decide_timeout`、`policy`
