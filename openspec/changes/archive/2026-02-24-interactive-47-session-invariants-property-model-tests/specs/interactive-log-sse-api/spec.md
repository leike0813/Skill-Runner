## MODIFIED Requirements

### Requirement: waiting_user 与终态语义 MUST 满足 FCMP 配对不变量
系统 MUST 保证关键 FCMP 事件的配对关系与序约束。

#### Scenario: waiting_user 配对
- **WHEN** 输出 `conversation.state.changed(to=waiting_user)`
- **THEN** 同一事件序列中存在 `user.input.required`

#### Scenario: reply/auto-decide 配对
- **WHEN** 输出 `interaction.reply.accepted` 或 `interaction.auto_decide.timeout`
- **THEN** 后续输出 `conversation.state.changed(waiting_user->queued)` 且 `trigger` 与事件类型一致

### Requirement: FCMP 序列 MUST 单调连续
系统 MUST 维持 `chat_event.seq` 从 1 开始的单调连续序列。

#### Scenario: 单调连续 seq
- **WHEN** 客户端消费同一次 materialize 的 FCMP 序列
- **THEN** `seq` 无重复、无空洞、严格递增
